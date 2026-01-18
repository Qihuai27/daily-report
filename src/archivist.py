"""
学术简报与知识流转系统 - 档案员模块 (Archivist)

功能：
1. 解析简报中勾选 [x] 的论文
2. 同步到 Zotero（创建条目 + 添加笔记）
3. 下载 PDF 并重命名
4. (可选) 创建 Astro 笔记存根
"""

import argparse
import hashlib
import mimetypes
import re
import shutil
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import arxiv
import requests

import config as app_config
from config import (
    ARCHIVE_ROOT_DIR,
    BLOG_DIR,
    HISTORY_FILE,
    INBOX_DIR,
    PAPERS_DIR,
    ZOTERO_DEFAULT_COLLECTION,
    logger,
)


# ============================================================
# 简报解析
# ============================================================


def find_latest_brief() -> Optional[Path]:
    """找到最新的简报文件"""
    briefs = list(INBOX_DIR.glob("*-Brief*.md"))
    if not briefs:
        return None
    return max(briefs, key=lambda p: p.stat().st_mtime)


def parse_brief(filepath: Path) -> list[dict]:
    """解析简报，提取勾选的论文"""
    logger.info(f"解析简报: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 匹配勾选的论文块
    # 格式: ## - [x] [中文标题](arxiv_url)
    pattern = r"## - \[x\] \[([^\]]+)\]\((https?://arxiv\.org/abs/[^\)]+)\)"
    matches = re.findall(pattern, content)

    papers = []
    for title_cn, arxiv_url in matches:
        arxiv_id = arxiv_url.split("/")[-1]

        # 提取该论文块的更多信息
        paper_block_pattern = rf"^## - \[x\] \[{re.escape(title_cn)}\].*?(?=^## - \[|^# |\Z)"
        block_match = re.search(paper_block_pattern, content, re.DOTALL | re.MULTILINE)

        paper_info = {
            "title_cn": title_cn,
            "arxiv_url": arxiv_url,
            "arxiv_id": arxiv_id,
        }

        if block_match:
            block = block_match.group(0)

            # 提取原题
            title_en_match = re.search(r"\*\*原题\*\*：\*([^*]+)\*", block)
            if title_en_match:
                paper_info["title_en"] = title_en_match.group(1)

            # 提取核心创新
            innovation_match = re.search(r"### 核心创新\n(.+?)(?=\n###|\n---|\Z)", block, re.DOTALL)
            if innovation_match:
                paper_info["innovation"] = innovation_match.group(1).strip()

            # 提取问题形式化
            formulation = {}
            for field in ["Input", "Output", "Objective", "Challenge"]:
                field_match = re.search(rf"\*\*{field}\*\*: (.+)", block)
                if field_match:
                    formulation[field.lower()] = field_match.group(1).strip()
            paper_info["formulation"] = formulation

            # 提取 PDF URL
            pdf_match = re.search(r"\[PDF\]\((https?://[^\)]+)\)", block)
            if pdf_match:
                paper_info["pdf_url"] = pdf_match.group(1)

            # 提取标签
            tags_match = re.search(r"### 标签\n(.+?)(?=\n###|\n---|\Z)", block, re.DOTALL)
            if tags_match:
                tags = re.findall(r"`#(\w+)`", tags_match.group(1))
                paper_info["tags"] = tags

        papers.append(paper_info)

    logger.info(f"找到 {len(papers)} 篇勾选的论文")
    return papers


# ============================================================
# ArXiv 元数据补全
# ============================================================


def fetch_arxiv_metadata(arxiv_id: str) -> Optional[dict]:
    """从 ArXiv 获取完整元数据"""
    logger.info(f"获取元数据: {arxiv_id}")

    try:
        client = arxiv.Client()
        search = arxiv.Search(id_list=[arxiv_id])
        results = list(client.results(search))

        if not results:
            logger.warning(f"未找到论文: {arxiv_id}")
            return None

        paper = results[0]
        return {
            "arxiv_id": arxiv_id,
            "title": paper.title,
            "abstract": paper.summary,
            "authors": [str(a) for a in paper.authors],
            "published": paper.published.strftime("%Y-%m-%d"),
            "pdf_url": paper.pdf_url,
            "categories": paper.categories,
            "doi": paper.doi,
        }

    except Exception as e:
        logger.error(f"获取元数据失败 ({arxiv_id}): {e}")
        return None


# ============================================================
# Zotero 同步
# ============================================================


def normalize_attachment_mode(mode: Optional[str]) -> str:
    """标准化附件模式"""
    mode = (mode or "none").strip().lower()
    if mode not in {"none", "upload", "linked", "both"}:
        return "none"
    return mode


def attachment_mode_flags(mode: Optional[str]) -> set[str]:
    """返回附件模式集合"""
    mode = normalize_attachment_mode(mode)
    if mode == "both":
        return {"upload", "linked"}
    if mode == "none":
        return set()
    return {mode}


def compute_md5(file_path: Path) -> str:
    """计算文件 MD5"""
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            md5.update(chunk)
    return md5.hexdigest()


def guess_content_type(file_path: Path) -> str:
    """推断文件 MIME 类型"""
    content_type, _ = mimetypes.guess_type(str(file_path))
    return content_type or "application/pdf"


def linked_archive_dir(linked_root: Path, date_str: Optional[str] = None) -> Path:
    """Linked 附件归档目录: <linked_root>/daily-report/YYYY-MM-DD"""
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    return linked_root / "daily-report" / date_str


def move_to_linked_dir(pdf_path: Path, linked_root: Path, date_str: Optional[str] = None) -> Path:
    """将 PDF 移动到 Linked 附件目录"""
    target_dir = linked_archive_dir(linked_root, date_str)
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        pdf_path.resolve().relative_to(target_dir.resolve())
        return pdf_path
    except ValueError:
        pass

    target = target_dir / pdf_path.name
    if target.exists():
        logger.info(f"Linked 目录已存在同名文件，使用现有文件: {target}")
        return target

    try:
        shutil.move(str(pdf_path), str(target))
        return target
    except Exception as e:
        logger.warning(f"移动到 Linked 目录失败: {e}")
        return pdf_path


class ZoteroClient:
    """Zotero API 客户端"""

    BASE_URL = "https://api.zotero.org"

    def __init__(
        self,
        api_key: Optional[str] = None,
        user_id: Optional[str] = None,
        library_type: Optional[str] = None,
    ):
        self.api_key = api_key if api_key is not None else app_config.ZOTERO_API_KEY
        self.user_id = user_id if user_id is not None else app_config.ZOTERO_USER_ID
        self.library_type = library_type if library_type is not None else app_config.ZOTERO_LIBRARY_TYPE

        if not self.api_key or not self.user_id:
            raise ValueError("请设置 ZOTERO_API_KEY 和 ZOTERO_USER_ID 环境变量")

        self.headers = {
            "Zotero-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def _get_library_url(self) -> str:
        if self.library_type == "user":
            return f"{self.BASE_URL}/users/{self.user_id}"
        else:
            return f"{self.BASE_URL}/groups/{self.user_id}"

    def get_collections(self) -> list[dict]:
        """获取所有收藏集"""
        url = f"{self._get_library_url()}/collections"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def find_or_create_collection(self, name: str) -> str:
        """查找或创建收藏集，返回 collection key"""
        collections = self.get_collections()

        # 查找现有收藏集
        for col in collections:
            if col["data"]["name"] == name:
                return col["key"]

        # 创建新收藏集
        url = f"{self._get_library_url()}/collections"
        payload = [{"name": name}]
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()

        result = response.json()
        if "successful" in result and "0" in result["successful"]:
            return result["successful"]["0"]["key"]

        raise Exception(f"创建收藏集失败: {result}")

    def create_item(self, item_data: dict, collection_key: Optional[str] = None) -> dict:
        """创建条目"""
        url = f"{self._get_library_url()}/items"

        if collection_key:
            item_data["collections"] = [collection_key]

        payload = [item_data]
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()

        result = response.json()
        if "successful" in result and "0" in result["successful"]:
            return result["successful"]["0"]

        logger.error(f"创建条目失败: {result}")
        return {}

    def create_attachment_item(self, attachment_data: dict) -> dict:
        """创建附件条目"""
        url = f"{self._get_library_url()}/items"
        payload = [attachment_data]
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()

        result = response.json()
        if "successful" in result and "0" in result["successful"]:
            return result["successful"]["0"]

        logger.error(f"创建附件失败: {result}")
        return {}

    def add_note(self, parent_key: str, note_content: str) -> dict:
        """添加笔记附件"""
        url = f"{self._get_library_url()}/items"

        note_data = {
            "itemType": "note",
            "parentItem": parent_key,
            "note": note_content,
        }

        payload = [note_data]
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()

        result = response.json()
        return result.get("successful", {}).get("0", {})

    def request_upload_authorization(
        self,
        item_key: str,
        filename: str,
        filesize: int,
        md5: str,
        mtime_ms: int,
    ) -> dict:
        """请求上传授权"""
        url = f"{self._get_library_url()}/items/{item_key}/file"
        payload = {
            "md5": md5,
            "filename": filename,
            "filesize": filesize,
            "mtime": mtime_ms,
            "params": 1,
        }
        headers = {"Zotero-API-Key": self.api_key, "If-None-Match": "*"}
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        return response.json()

    def upload_file_to_storage(self, upload_info: dict, file_path: Path, content_type: str) -> None:
        """上传文件到存储服务"""
        url = upload_info.get("url")
        if not url:
            raise ValueError("上传信息缺少 URL")

        params = upload_info.get("params")
        if params:
            data = {item["name"]: item["value"] for item in params}
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, content_type)}
                response = requests.post(url, data=data, files=files)
                response.raise_for_status()
            return

        prefix = upload_info.get("prefix", "")
        suffix = upload_info.get("suffix", "")
        if prefix or suffix:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            body = prefix.encode("utf-8") + file_bytes + suffix.encode("utf-8")
            response = requests.post(url, data=body, headers={"Content-Type": upload_info.get("contentType", content_type)})
            response.raise_for_status()
            return

        raise ValueError("上传信息缺少 params/prefix/suffix")

    def register_upload(self, item_key: str, upload_key: str) -> None:
        """注册上传完成"""
        url = f"{self._get_library_url()}/items/{item_key}/file"
        payload = {"upload": upload_key}
        headers = {"Zotero-API-Key": self.api_key, "If-None-Match": "*"}
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()

    def upload_attachment_file(self, item_key: str, file_path: Path, content_type: str) -> bool:
        """上传附件文件"""
        md5 = compute_md5(file_path)
        stat = file_path.stat()
        filesize = stat.st_size
        mtime_ms = int(stat.st_mtime * 1000)

        upload_info = self.request_upload_authorization(
            item_key=item_key,
            filename=file_path.name,
            filesize=filesize,
            md5=md5,
            mtime_ms=mtime_ms,
        )

        if upload_info.get("exists"):
            return True

        self.upload_file_to_storage(upload_info, file_path, content_type)
        upload_key = upload_info.get("uploadKey")
        if not upload_key:
            raise ValueError("上传信息缺少 uploadKey")

        self.register_upload(item_key, upload_key)
        return True

    def create_linked_attachment(self, parent_key: str, file_path: Path, content_type: str) -> dict:
        """创建 Linked 附件"""
        attachment_data = {
            "itemType": "attachment",
            "parentItem": parent_key,
            "linkMode": "linked_file",
            "title": file_path.stem,
            "path": str(file_path),
            "contentType": content_type,
        }
        return self.create_attachment_item(attachment_data)


def build_zotero_item(paper: dict, metadata: dict) -> dict:
    """构建 Zotero 条目数据"""
    # 使用 preprint 类型
    item = {
        "itemType": "preprint",
        "title": metadata.get("title", paper.get("title_en", "")),
        "abstractNote": metadata.get("abstract", ""),
        "repository": "arXiv",
        "archiveID": paper["arxiv_id"],
        "url": paper["arxiv_url"],
        "date": metadata.get("published", ""),
    }

    # 添加作者
    creators = []
    for author in metadata.get("authors", []):
        parts = author.rsplit(" ", 1)
        if len(parts) == 2:
            creators.append({
                "creatorType": "author",
                "firstName": parts[0],
                "lastName": parts[1],
            })
        else:
            creators.append({
                "creatorType": "author",
                "name": author,
            })
    item["creators"] = creators

    # 添加 DOI
    if metadata.get("doi"):
        item["DOI"] = metadata["doi"]

    # 在 Extra 字段存储 AI 分析结果
    extra_parts = []
    if paper.get("title_cn"):
        extra_parts.append(f"中文标题: {paper['title_cn']}")
    if paper.get("innovation"):
        extra_parts.append(f"核心创新: {paper['innovation']}")
    if paper.get("tags"):
        extra_parts.append(f"标签: {', '.join(paper['tags'])}")

    if extra_parts:
        item["extra"] = "\n".join(extra_parts)

    return item


def build_note_content(paper: dict) -> str:
    """构建 Zotero 笔记内容（HTML 格式）"""
    formulation = paper.get("formulation", {})

    note = f"""
<h2>AI 分析摘要</h2>

<h3>核心创新</h3>
<p>{paper.get('innovation', 'N/A')}</p>

<h3>问题形式化</h3>
<ul>
<li><b>Input</b>: {formulation.get('input', 'N/A')}</li>
<li><b>Output</b>: {formulation.get('output', 'N/A')}</li>
<li><b>Objective</b>: {formulation.get('objective', 'N/A')}</li>
<li><b>Challenge</b>: {formulation.get('challenge', 'N/A')}</li>
</ul>

<h3>标签</h3>
<p>{', '.join(paper.get('tags', []))}</p>

<hr/>
<p><i>由学术简报系统自动生成</i></p>
"""
    return note.strip()


def sync_to_zotero(
    papers: list[dict],
    collection_name: str = ZOTERO_DEFAULT_COLLECTION,
    pdf_paths: Optional[dict[str, Path]] = None,
    attachment_mode: Optional[str] = None,
    linked_dir: Optional[Path] = None,
) -> list[str]:
    """同步论文到 Zotero"""
    if not app_config.ZOTERO_API_KEY or not app_config.ZOTERO_USER_ID:
        logger.warning("Zotero API 未配置，跳过同步")
        return []

    client = ZoteroClient(
        api_key=app_config.ZOTERO_API_KEY,
        user_id=app_config.ZOTERO_USER_ID,
        library_type=app_config.ZOTERO_LIBRARY_TYPE,
    )
    synced_keys = []
    mode_flags = attachment_mode_flags(attachment_mode or app_config.ZOTERO_ATTACHMENT_MODE)
    linked_dir = linked_dir or (Path(app_config.ZOTERO_LINKED_DIR) if app_config.ZOTERO_LINKED_DIR else None)
    pdf_paths = pdf_paths or {}

    # 获取或创建收藏集
    try:
        collection_key = client.find_or_create_collection(collection_name)
        logger.info(f"使用收藏集: {collection_name} ({collection_key})")
    except Exception as e:
        logger.error(f"获取收藏集失败: {e}")
        collection_key = None

    for paper in papers:
        logger.info(f"同步到 Zotero: {paper['arxiv_id']}")

        # 获取完整元数据
        metadata = fetch_arxiv_metadata(paper["arxiv_id"])
        if not metadata:
            continue

        if not paper.get("pdf_url") and metadata.get("pdf_url"):
            paper["pdf_url"] = metadata["pdf_url"]

        # 构建条目
        item_data = build_zotero_item(paper, metadata)

        try:
            # 创建条目
            result = client.create_item(item_data, collection_key)
            if not result:
                continue

            item_key = result.get("key")
            logger.info(f"条目已创建: {item_key}")

            # 添加 AI 分析笔记
            if paper.get("innovation") or paper.get("formulation"):
                note_content = build_note_content(paper)
                client.add_note(item_key, note_content)
                logger.info(f"笔记已添加")

            # 添加附件
            if mode_flags:
                pdf_path = pdf_paths.get(paper["arxiv_id"])
                if not pdf_path:
                    pdf_path = download_pdf(paper)
                if pdf_path and "linked" in mode_flags and linked_dir:
                    pdf_path = move_to_linked_dir(pdf_path, linked_dir)
                    pdf_paths[paper["arxiv_id"]] = pdf_path

                if not pdf_path:
                    logger.warning(f"未找到 PDF，跳过附件: {paper['arxiv_id']}")
                else:
                    content_type = guess_content_type(pdf_path)

                    if "linked" in mode_flags:
                        if not linked_dir:
                            logger.warning("Linked 附件目录未配置，跳过 linked 附件")
                        else:
                            try:
                                linked_result = client.create_linked_attachment(item_key, pdf_path, content_type)
                                if linked_result:
                                    logger.info("Linked 附件已创建")
                                else:
                                    logger.warning("Linked 附件创建失败：未返回条目")
                            except Exception as e:
                                logger.warning(f"Linked 附件创建失败: {e}")

                    if "upload" in mode_flags:
                        try:
                            attachment_data = {
                                "itemType": "attachment",
                                "parentItem": item_key,
                                "linkMode": "imported_file",
                                "title": pdf_path.stem,
                                "filename": pdf_path.name,
                                "contentType": content_type,
                            }
                            attachment_result = client.create_attachment_item(attachment_data)
                            attachment_key = attachment_result.get("key")
                            if attachment_key:
                                client.upload_attachment_file(attachment_key, pdf_path, content_type)
                                logger.info("PDF 已上传到 Zotero")
                            else:
                                logger.warning("PDF 上传失败：附件条目未创建")
                        except Exception as e:
                            logger.warning(f"上传附件失败: {e}")

            synced_keys.append(item_key)

        except Exception as e:
            logger.error(f"同步失败 ({paper['arxiv_id']}): {e}")

        time.sleep(0.5)  # 避免 API 限流

    return synced_keys


# ============================================================
# PDF 下载
# ============================================================


def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """清理文件名"""
    # Unicode 规范化
    filename = unicodedata.normalize("NFKC", filename)

    # 移除/替换非法字符
    filename = re.sub(r'[<>:"/\\|?*]', "", filename)
    filename = re.sub(r"\s+", "_", filename)
    filename = re.sub(r"_+", "_", filename)

    # 限制长度
    if len(filename) > max_length:
        filename = filename[:max_length]

    return filename.strip("_")


def default_archive_dir(date_str: Optional[str] = None) -> Path:
    """默认归档目录: ~/daily-report/arxiv/YYYY-MM-DD"""
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    return ARCHIVE_ROOT_DIR / date_str


def ensure_public_copy(pdf_path: Path) -> Optional[Path]:
    """将 PDF 复制到 public/papers，供 Astro 使用"""
    if not pdf_path or not pdf_path.exists():
        return None
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    target = PAPERS_DIR / pdf_path.name
    if target.exists():
        return target
    try:
        shutil.copy2(pdf_path, target)
        return target
    except Exception as e:
        logger.warning(f"复制到 public/papers 失败: {e}")
        return None


def download_pdf(paper: dict, output_dir: Optional[Path] = None) -> Optional[Path]:
    """下载 PDF 并重命名"""
    if output_dir is None:
        output_dir = default_archive_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_url = paper.get("pdf_url")
    if not pdf_url:
        arxiv_url = paper.get("arxiv_url", "")
        if arxiv_url:
            pdf_url = arxiv_url.replace("/abs/", "/pdf/")
        elif paper.get("arxiv_id"):
            pdf_url = f"https://arxiv.org/pdf/{paper['arxiv_id']}"
    if not pdf_url:
        logger.warning(f"无 PDF URL: {paper['arxiv_id']}")
        return None

    # 生成文件名
    title = paper.get("title_en", paper.get("title_cn", paper["arxiv_id"]))
    safe_name = sanitize_filename(title)
    filename = f"{safe_name}.pdf"
    filepath = output_dir / filename

    # 检查是否已存在
    if filepath.exists():
        logger.info(f"PDF 已存在: {filepath}")
        return filepath

    logger.info(f"下载 PDF: {pdf_url}")

    try:
        response = requests.get(pdf_url, stream=True, timeout=60)
        response.raise_for_status()

        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"PDF 已保存: {filepath}")
        return filepath

    except Exception as e:
        logger.error(f"下载失败: {e}")
    return None


# ============================================================
# Astro 笔记存根
# ============================================================


def create_astro_stub(paper: dict, pdf_path: Optional[Path] = None) -> Optional[Path]:
    """创建 Astro 博客笔记存根"""
    title = paper.get("title_cn", paper.get("title_en", "Untitled"))
    safe_name = sanitize_filename(title)
    filename = f"{safe_name}.md"
    filepath = BLOG_DIR / filename

    if filepath.exists():
        logger.info(f"笔记已存在: {filepath}")
        return filepath

    # 构建 frontmatter
    pdf_relative = f"/papers/{pdf_path.name}" if pdf_path else ""
    tags_yaml = "\n".join([f"  - {tag}" for tag in paper.get("tags", [])])

    content = f"""---
title: "{title}"
pubDate: {datetime.now().strftime("%Y-%m-%d")}
description: "{paper.get('innovation', '')[:100]}"
arxiv: "{paper['arxiv_url']}"
pdf: "{pdf_relative}"
tags:
{tags_yaml}
draft: true
---

## 论文信息

- **ArXiv ID**: {paper['arxiv_id']}
- **原题**: {paper.get('title_en', '')}
- **链接**: [{paper['arxiv_url']}]({paper['arxiv_url']})

## AI 分析摘要

### 核心创新

{paper.get('innovation', 'TODO')}

### 问题形式化

- **Input**: {paper.get('formulation', {}).get('input', '')}
- **Output**: {paper.get('formulation', {}).get('output', '')}
- **Objective**: {paper.get('formulation', {}).get('objective', '')}
- **Challenge**: {paper.get('formulation', {}).get('challenge', '')}

## 精读笔记

TODO: 添加你的阅读笔记

## 关键引用

TODO: 记录重要的引用

"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"笔记存根已创建: {filepath}")
    return filepath


# ============================================================
# 历史记录更新
# ============================================================


def update_history(arxiv_id: str, status: str = "synced") -> None:
    """更新历史记录"""
    import json

    record = {
        "id": arxiv_id,
        "date_fetched": datetime.now().strftime("%Y-%m-%d"),
        "status": status,
    }

    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ============================================================
# 主函数
# ============================================================


def main():
    parser = argparse.ArgumentParser(description="学术简报档案员 - 同步勾选的论文")
    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        help="指定简报文件路径（默认使用最新的）",
    )
    parser.add_argument(
        "--no-zotero",
        action="store_true",
        help="跳过 Zotero 同步",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="跳过 PDF 下载",
    )
    parser.add_argument(
        "--no-astro",
        action="store_true",
        help="跳过 Astro 笔记创建",
    )
    parser.add_argument(
        "--collection",
        default=ZOTERO_DEFAULT_COLLECTION,
        help="Zotero 收藏集名称",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("学术简报档案员")
    print("=" * 60)

    # 1. 找到简报文件
    if args.file:
        brief_path = args.file
    else:
        brief_path = find_latest_brief()

    if not brief_path or not brief_path.exists():
        print("未找到简报文件，请先运行 reporter.py")
        return

    print(f"\n处理简报: {brief_path}")

    # 2. 解析勾选的论文
    papers = parse_brief(brief_path)

    if not papers:
        print("未找到勾选的论文 [x]")
        return

    print(f"\n找到 {len(papers)} 篇勾选的论文:")
    for p in papers:
        print(f"  - {p['arxiv_id']}: {p['title_cn'][:40]}...")

    # 3. Zotero 同步
    attachment_mode = normalize_attachment_mode(app_config.ZOTERO_ATTACHMENT_MODE)
    mode_flags = attachment_mode_flags(attachment_mode)
    linked_dir = Path(app_config.ZOTERO_LINKED_DIR) if app_config.ZOTERO_LINKED_DIR else None

    # 3. PDF 下载
    pdf_paths = {}
    public_paths = {}
    should_download = (not args.no_pdf) or bool(mode_flags)
    if should_download:
        if args.no_pdf and mode_flags:
            logger.warning("附件需要 PDF，忽略 --no-pdf，仍会下载用于附件")
        print("\n下载 PDF...")
        for paper in papers:
            pdf_path = download_pdf(paper)
            if pdf_path and "linked" in mode_flags and linked_dir:
                pdf_path = move_to_linked_dir(pdf_path, linked_dir)
            if pdf_path:
                pdf_paths[paper["arxiv_id"]] = pdf_path
                if not args.no_astro:
                    public_path = ensure_public_copy(pdf_path)
                    if public_path:
                        public_paths[paper["arxiv_id"]] = public_path
        print(f"成功下载 {len(pdf_paths)} 个 PDF")
    else:
        print("\n跳过 PDF 下载")

    # 4. Zotero 同步
    if not args.no_zotero:
        print("\n同步到 Zotero...")
        synced = sync_to_zotero(
            papers,
            args.collection,
            pdf_paths=pdf_paths,
            attachment_mode=attachment_mode,
            linked_dir=linked_dir,
        )
        print(f"成功同步 {len(synced)} 篇")
    else:
        print("\n跳过 Zotero 同步")

    # 5. Astro 笔记存根
    if not args.no_astro:
        print("\n创建 Astro 笔记存根...")
        for paper in papers:
            pdf_path = public_paths.get(paper["arxiv_id"])
            create_astro_stub(paper, pdf_path)
        print(f"创建 {len(papers)} 个笔记存根")
    else:
        print("\n跳过 Astro 笔记创建")

    # 6. 更新历史记录
    for paper in papers:
        update_history(paper["arxiv_id"], "synced")

    print("\n" + "=" * 60)
    print("处理完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
