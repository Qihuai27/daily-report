"""
学术简报与知识流转系统 - 情报官模块 (Reporter)

功能：
1. 从 ArXiv 抓取最新论文
2. 去重（基于历史记录）
3. 调用 LLM 进行深度解析
4. 生成结构化 Markdown 简报
"""

import argparse
import json
import re
import time
import tarfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

import arxiv
import requests

import config
from config import (
    ANALYSIS_CACHE_DIR,
    DEFAULT_SEARCH_QUERIES,
    HISTORY_FILE,
    INBOX_DIR,
    MAX_RESULTS_PER_QUERY,
    MAX_TOTAL_RESULTS,
    SCORE_THRESHOLD,
    SORT_BY,
    logger,
)
from prompts import (
    BRIEF_HEADER_TEMPLATE,
    SYSTEM_PROMPT,
    build_analysis_prompt,
    format_paper_brief,
)
from user_config import load_template

try:
    import pdfplumber
except Exception:  # pragma: no cover - optional dependency
    pdfplumber = None

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - fallback for older installs
    try:
        from PyPDF2 import PdfReader  # type: ignore
    except Exception:  # pragma: no cover
        PdfReader = None

try:
    from pylatexenc.latex2text import LatexNodes2Text
except Exception:  # pragma: no cover - optional dependency
    LatexNodes2Text = None


# ============================================================ 
# 历史记录管理
# ============================================================ 


def load_history() -> set[str]:
    """加载已处理过的 ArXiv ID"""
    history = set()
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        history.add(record.get("id", ""))
                    except json.JSONDecodeError:
                        continue
    return history


def save_to_history(arxiv_id: str, status: str = "processed") -> None:
    """保存处理记录"""
    record = {
        "id": arxiv_id,
        "date_fetched": datetime.now().strftime("%Y-%m-%d"),
        "status": status,
    }
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ============================================================
# 分析缓存
# ============================================================


def _analysis_cache_path(arxiv_id: str) -> Path:
    safe_id = arxiv_id.replace("/", "_")
    return ANALYSIS_CACHE_DIR / f"{safe_id}.json"


def load_analysis_cache(arxiv_id: str) -> Optional[dict]:
    path = _analysis_cache_path(arxiv_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_analysis_cache(paper: dict) -> None:
    arxiv_id = paper.get("arxiv_id")
    if not arxiv_id:
        return
    path = _analysis_cache_path(arxiv_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(paper, f, ensure_ascii=False, indent=2)
    except Exception:
        return


def _parse_date_arg(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y%m%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期格式应为 YYYY-MM-DD") from exc


# ============================================================ 
# ArXiv 抓取
# ============================================================ 


def _normalize_date_str(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    if re.fullmatch(r"\d{8}", value):
        return value
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y%m%d")
    except ValueError:
        return value


def _build_query_with_date(query: str, date_from: Optional[str], date_to: Optional[str]) -> str:
    date_from = _normalize_date_str(date_from)
    date_to = _normalize_date_str(date_to)
    if not date_from and not date_to:
        return query

    if date_from and not date_to:
        date_to = datetime.now().strftime("%Y%m%d")
    if date_to and not date_from:
        date_from = date_to

    return f"({query}) AND submittedDate:[{date_from} TO {date_to}]"


def _quote_phrase(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if cleaned.startswith('"') and cleaned.endswith('"') and len(cleaned) >= 2:
        cleaned = cleaned[1:-1]
    cleaned = cleaned.replace('"', '\\"')
    return f"\"{cleaned}\""


def build_keyword_query(keywords: list[str], template_id: Optional[str] = None) -> str:
    cleaned = [kw.strip() for kw in keywords if kw and kw.strip()]
    if not cleaned:
        return ""
    phrases = [_quote_phrase(kw) for kw in cleaned]

    if template_id == "title_abs_and":
        parts = [f"(ti:{p} OR abs:{p})" for p in phrases]
    elif template_id == "title_and":
        parts = [f"ti:{p}" for p in phrases]
    elif template_id == "abs_and":
        parts = [f"abs:{p}" for p in phrases]
    else:
        parts = phrases

    return " AND ".join(parts)


def fetch_arxiv_papers(
    queries: list[str],
    max_per_query: int = MAX_RESULTS_PER_QUERY,
    max_total: int = MAX_TOTAL_RESULTS,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    query_template_id: Optional[str] = None,
    cancel_cb: Optional[callable] = None,
) -> list[dict]:
    """从 ArXiv 抓取论文"""
    logger.info(f"开始抓取论文，关键词: {queries}")

    all_papers = []
    seen_ids = set()

    client = arxiv.Client()

    query = build_keyword_query(queries, query_template_id)
    if not query:
        logger.warning("关键词为空，跳过抓取")
        return []

    query_with_date = _build_query_with_date(query, date_from, date_to)
    logger.info(f"正在搜索: {query_with_date}")

    max_results = max_total if max_total > 0 else max_per_query

    # 构建搜索对象
    search = arxiv.Search(
        query=query_with_date,
        max_results=max_results,
        sort_by=getattr(
            arxiv.SortCriterion,
            SORT_BY.replace("D", "_d").title().replace("_d", "D"),
            arxiv.SortCriterion.SubmittedDate,
        ),
        sort_order=arxiv.SortOrder.Descending,
    )

    try:
        for paper in client.results(search):
            if cancel_cb and cancel_cb():
                logger.info("抓取取消请求已收到，终止搜索")
                break

            arxiv_id = paper.entry_id.split("/")[-1]
            if arxiv_id in seen_ids:
                continue
            seen_ids.add(arxiv_id)

            paper_info = {
                "arxiv_id": arxiv_id,
                "title_en": paper.title,
                "abstract": paper.summary.replace("\n", " "),
                "authors": [str(a) for a in paper.authors],
                "published": paper.published.strftime("%Y-%m-%d"),
                "arxiv_url": paper.entry_id,
                "pdf_url": paper.pdf_url,
                "categories": paper.categories,
            }
            if load_analysis_cache(arxiv_id):
                paper_info["cached_analysis"] = True
            all_papers.append(paper_info)

            if len(all_papers) >= max_results:
                break
    except Exception as e:
        logger.error(f"抓取失败 ({query_with_date}): {e}")
        return []

    logger.info(f"抓取完成，共 {len(all_papers)} 篇论文")
    return all_papers


# ============================================================ 
# LLM 调用
# ============================================================ 


def call_llm(prompt: str, system_prompt: str = SYSTEM_PROMPT) -> Optional[str]:
    """调用 LLM API"""
    provider = config.LLM_PROVIDER.lower()

    try:
        if provider == "openai":
            return _call_openai(prompt, system_prompt)
        elif provider == "anthropic":
            return _call_anthropic(prompt, system_prompt)
        elif provider == "gemini":
            return _call_gemini(prompt, system_prompt)
        elif provider == "ollama":
            return _call_ollama(prompt, system_prompt)
        else:
            logger.error(f"不支持的 LLM provider: {provider}")
            return None
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        return None


def _normalize_openai_base_url(base_url: str) -> str:
    """移除误配置的路径后缀，确保 base_url 以 /v1 结尾"""
    if not base_url:
        return base_url
    for suffix in ("/chat/completions", "/completions"):
        if base_url.endswith(suffix):
            base_url = base_url[: -len(suffix)]
            break
    return base_url.rstrip("/")


def _call_openai(prompt: str, system_prompt: str) -> Optional[str]:
    """调用 OpenAI API"""
    from openai import OpenAI

    base_url = _normalize_openai_base_url(config.OPENAI_BASE_URL)
    client = OpenAI(api_key=config.OPENAI_API_KEY, base_url=base_url or None)

    # 注意：移除 response_format 以兼容更多 API 代理
    response = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )

    return response.choices[0].message.content

def _call_anthropic(prompt: str, system_prompt: str) -> Optional[str]:
    """调用 Anthropic API"""
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text

def _call_ollama(prompt: str, system_prompt: str) -> Optional[str]:
    """调用 Ollama API (本地)"""
    import requests

    response = requests.post(
        f"{config.OLLAMA_BASE_URL}/api/generate",
        json={
            "model": config.OLLAMA_MODEL,
            "prompt": f"{system_prompt}\n\n{prompt}",
            "stream": False,
            "format": "json",
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json().get("response", "")

def _call_gemini(prompt: str, system_prompt: str) -> Optional[str]:
    """调用 Gemini API"""
    import requests

    if not config.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY 未配置")

    base_url = config.GEMINI_BASE_URL.strip() if config.GEMINI_BASE_URL else "https://generativelanguage.googleapis.com/v1beta"
    base_url = base_url.rstrip("/")
    model = config.GEMINI_MODEL or "gemini-1.5-pro"
    url = f"{base_url}/models/{model}:generateContent"

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"{system_prompt}\n\n{prompt}"}],
            }
        ],
        "generationConfig": {"temperature": 0.3},
    }

    response = requests.post(
        url,
        params={"key": config.GEMINI_API_KEY},
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()

    candidates = data.get("candidates") or []
    if not candidates:
        return None
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        return None
    return parts[0].get("text", "")

def _try_parse_json(text: str) -> Optional[dict]:
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 修正常见问题：尾逗号 + 非法反斜杠转义（如 \in、\mathbb）
    fixed = re.sub(r",\s*([}\]])", r"\1", text)
    fixed = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", fixed)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        return None

def parse_llm_response(response: str) -> Optional[dict]:
    """解析 LLM 返回的 JSON"""
    if not response:
        return None

    # 清理响应文本
    response = response.strip()

    # 尝试直接解析
    parsed = _try_parse_json(response)
    if parsed is not None:
        return parsed

    # 尝试提取 ```json ... ``` 代码块
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
    if json_match:
        parsed = _try_parse_json(json_match.group(1))
        if parsed is not None:
            return parsed

    # 尝试找到最外层的 { } 块（贪婪匹配）
    brace_match = re.search(r"{[\s\S]*}", response)
    if brace_match:
        json_str = brace_match.group(0)
        parsed = _try_parse_json(json_str)
        if parsed is not None:
            return parsed

    # 最后尝试：逐行解析，找到有效 JSON
    lines = response.split("\n")
    json_lines = []
    in_json = False
    brace_count = 0

    for line in lines:
        if "{" in line and not in_json:
            in_json = True
        if in_json:
            json_lines.append(line)
            brace_count += line.count("{") - line.count("}")
            if brace_count <= 0:
                break

    if json_lines:
        parsed = _try_parse_json("\n".join(json_lines))
        if parsed is not None:
            return parsed

    logger.warning(f"无法解析 LLM 响应: {response[:200]}...")
    return None


# ============================================================ 
# 论文分析
# ============================================================ 

INTRO_PATTERNS = [
    r"\b1\s*\.?\s*introduction\b",
    r"\bintroduction\b",
    r"\b引言\b",
]
REF_PATTERNS = [
    r"\breferences\b",
    r"\bbibliography\b",
    r"\b参考文献\b",
    r"\bappendix\b",
]


def _clean_pdf_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"-\n([a-z])", r"\1", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _download_pdf_to_cache(paper: dict) -> Optional[Path]:
    pdf_url = paper.get("pdf_url")
    arxiv_id = paper.get("arxiv_id")
    if not pdf_url or not arxiv_id:
        return None

    cache_dir = config.LOGS_DIR / "pdf_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    global _PDF_CACHE_CLEANED
    if not _PDF_CACHE_CLEANED:
        _cleanup_cache(cache_dir, config.PDF_CACHE_TTL_DAYS)
        _PDF_CACHE_CLEANED = True
    filepath = cache_dir / f"{arxiv_id}.pdf"
    if filepath.exists():
        return filepath

    try:
        response = requests.get(pdf_url, stream=True, timeout=60)
        response.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return filepath
    except Exception as e:
        logger.warning(f"PDF 下载失败 ({arxiv_id}): {e}")
        return None


def _find_intro_page(text: str) -> bool:
    if re.search(r"\bcontents\b", text, flags=re.I):
        return False
    return any(re.search(pat, text, flags=re.I) for pat in INTRO_PATTERNS)


def _find_reference_page(text: str) -> bool:
    return any(re.search(pat, text, flags=re.I) for pat in REF_PATTERNS)


def _normalize_line_for_repeat(line: str) -> str:
    line = line.strip().lower()
    line = re.sub(r"\d+", "", line)
    line = re.sub(r"[^\w\u4e00-\u9fff\s]", "", line)
    line = re.sub(r"\s+", " ", line)
    return line


def _looks_like_page_number(line: str) -> bool:
    normalized = line.strip().lower()
    if re.fullmatch(r"\d+", normalized):
        return True
    if re.fullmatch(r"page\s*\d+(\s*/\s*\d+)?", normalized):
        return True
    if re.fullmatch(r"\d+\s*/\s*\d+", normalized):
        return True
    return False


def _extract_text_with_pdfplumber(page) -> str:
    try:
        text = page.extract_text(x_tolerance=2, y_tolerance=2, layout=True)
        if text:
            return text
    except Exception:
        pass
    try:
        return page.extract_text() or ""
    except Exception:
        return ""


def _extract_text_with_pypdf(page) -> str:
    try:
        return page.extract_text() or ""
    except Exception:
        return ""


def _extract_pdf_body_text(
    pdf_path: Path,
    max_body_pages: int = 15,
    max_tokens: int = 10000,
    intro_scan_pages: int = 12,
) -> Optional[str]:
    pages_text: List[List[str]] = []
    repeat_counter: Dict[str, int] = {}

    if pdfplumber is not None:
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                total_pages = len(pdf.pages)
                if total_pages == 0:
                    return None
                for i in range(total_pages):
                    text = _extract_text_with_pdfplumber(pdf.pages[i])
                    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                    pages_text.append(lines)
                    for ln in lines:
                        if len(ln) > 80:
                            continue
                        if _looks_like_page_number(ln):
                            continue
                        norm = _normalize_line_for_repeat(ln)
                        if not norm or len(norm) < 4:
                            continue
                        repeat_counter[norm] = repeat_counter.get(norm, 0) + 1
        except Exception as e:
            logger.warning(f"PDF 打开失败: {e}")
            return None
    elif PdfReader is not None:
        try:
            reader = PdfReader(str(pdf_path))
        except Exception as e:
            logger.warning(f"PDF 打开失败: {e}")
            return None

        total_pages = len(reader.pages)
        if total_pages == 0:
            return None

        for i in range(total_pages):
            text = _extract_text_with_pypdf(reader.pages[i])
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            pages_text.append(lines)
            for ln in lines:
                if len(ln) > 80:
                    continue
                if _looks_like_page_number(ln):
                    continue
                norm = _normalize_line_for_repeat(ln)
                if not norm or len(norm) < 4:
                    continue
                repeat_counter[norm] = repeat_counter.get(norm, 0) + 1
    else:
        logger.warning("PDF 解析依赖未安装，跳过正文读取")
        return None

    total_pages = len(pages_text)
    if total_pages == 0:
        return None

    intro_idx = None
    scan_limit = min(total_pages, max(1, intro_scan_pages))
    for i in range(scan_limit):
        text = "\n".join(pages_text[i])
        if _find_intro_page(text):
            intro_idx = i
            break

    if intro_idx is None:
        intro_idx = 1 if total_pages > 1 else 0

    body_pages = []
    end_limit = min(total_pages, intro_idx + max_body_pages)
    for i in range(intro_idx, end_limit):
        lines = pages_text[i]
        filtered_lines = []
        for ln in lines:
            if _looks_like_page_number(ln):
                continue
            if "arxiv:" in ln.lower():
                continue
            norm = _normalize_line_for_repeat(ln)
            if norm and repeat_counter.get(norm, 0) >= 3 and len(norm) <= 60:
                continue
            filtered_lines.append(ln)
        text = "\n".join(filtered_lines)
        if _find_reference_page(text) and i > intro_idx:
            break
        cleaned = _clean_pdf_text(text)
        if cleaned:
            body_pages.append(cleaned)

    if not body_pages:
        return None

    body_text = "\n\n".join(body_pages)
    max_chars = max_tokens * 4
    if len(body_text) > max_chars:
        trimmed = body_text[:max_chars]
        last_break = trimmed.rfind("\n\n")
        if last_break > max_chars * 0.7:
            trimmed = trimmed[:last_break]
        body_text = trimmed + "\n\n[已截断]"
    return body_text


def _trim_text_to_max_tokens(text: str, max_tokens: int) -> str:
    max_chars = max(400, max_tokens * 4)
    if len(text) <= max_chars:
        return text
    trimmed = text[:max_chars]
    last_break = trimmed.rfind("\n\n")
    if last_break > max_chars * 0.7:
        trimmed = trimmed[:last_break]
    return trimmed + "\n\n[已截断]"


def _download_arxiv_source_archive(arxiv_id: str) -> Optional[Path]:
    cache_dir = config.LOGS_DIR / "source_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    archive_path = cache_dir / f"{arxiv_id}.tar"
    if archive_path.exists():
        return archive_path

    url = f"https://arxiv.org/e-print/{arxiv_id}"
    max_bytes = max(1, config.ARXIV_SOURCE_MAX_MB) * 1024 * 1024

    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        downloaded = 0
        with open(archive_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                downloaded += len(chunk)
                if downloaded > max_bytes:
                    logger.warning(f"源码包过大，已中止: {arxiv_id}")
                    archive_path.unlink(missing_ok=True)
                    return None
                f.write(chunk)
        return archive_path
    except Exception as e:
        logger.warning(f"源码下载失败 ({arxiv_id}): {e}")
        archive_path.unlink(missing_ok=True)
        return None


_SOURCE_CACHE_CLEANED = False
_PDF_CACHE_CLEANED = False


def _cleanup_cache(cache_dir: Path, ttl_days: int) -> None:
    if ttl_days <= 0:
        return
    if not cache_dir.exists():
        return
    cutoff = datetime.now().timestamp() - ttl_days * 86400
    for path in cache_dir.iterdir():
        try:
            if path.stat().st_mtime >= cutoff:
                continue
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
        except Exception:
            continue


def _cleanup_source_cache(cache_dir: Path, ttl_days: int) -> None:
    _cleanup_cache(cache_dir, ttl_days)


def _prune_source_artifacts(cache_dir: Path, arxiv_id: str) -> None:
    if config.ARXIV_SOURCE_KEEP_ARCHIVE:
        return
    archive_path = cache_dir / f"{arxiv_id}.tar"
    extract_dir = cache_dir / arxiv_id
    try:
        archive_path.unlink(missing_ok=True)
    except Exception:
        pass
    if extract_dir.exists():
        shutil.rmtree(extract_dir, ignore_errors=True)


def _safe_extract_tar(archive_path: Path, extract_dir: Path) -> bool:
    try:
        with tarfile.open(archive_path, "r:*") as tar:
            members = tar.getmembers()
            total_size = sum(m.size for m in members)
            max_bytes = max(1, config.ARXIV_SOURCE_MAX_MB) * 1024 * 1024
            if total_size > max_bytes:
                logger.warning(f"源码解包过大，跳过: {archive_path.name}")
                return False

            extract_dir.mkdir(parents=True, exist_ok=True)
            base = extract_dir.resolve()
            safe_members = []
            for m in members:
                if not m.isreg():
                    continue
                target = (extract_dir / m.name).resolve()
                try:
                    target.relative_to(base)
                except ValueError:
                    continue
                safe_members.append(m)
            tar.extractall(path=extract_dir, members=safe_members)
        return True
    except Exception as e:
        logger.warning(f"源码解包失败 ({archive_path.name}): {e}")
        return False


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        try:
            return path.read_text(encoding="latin-1", errors="ignore")
        except Exception:
            return ""


def _strip_tex_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        lines.append(re.sub(r"(?<!\\)%.*", "", line))
    return "\n".join(lines)


def _select_main_tex(tex_paths: list[Path]) -> Optional[Path]:
    best_path = None
    best_score = -1
    for path in tex_paths:
        content = _read_text_file(path)
        if not content:
            continue
        score = 0
        if "\\begin{document}" in content:
            score += 1000
        if "\\documentclass" in content:
            score += 200
        if "\\end{document}" in content:
            score += 100
        score += min(len(content) // 1000, 200)
        if score > best_score:
            best_score = score
            best_path = path
    return best_path


_INPUT_PATTERN = re.compile(r"\\(?:input|include|subfile)\{([^}]+)\}")


def _resolve_tex_ref(ref: str, base_dir: Path) -> Optional[Path]:
    ref = ref.strip().strip('"').strip("'")
    if not ref or ref.startswith("http"):
        return None
    candidates = [
        base_dir / ref,
        base_dir / f"{ref}.tex",
    ]
    for cand in candidates:
        if cand.exists():
            return cand
    return None


def _expand_tex_inputs(text: str, base_dir: Path, seen: set[Path], depth: int = 0) -> str:
    if depth > 8:
        return text

    def repl(match: re.Match) -> str:
        ref = match.group(1)
        tex_path = _resolve_tex_ref(ref, base_dir)
        if not tex_path or tex_path in seen:
            return ""
        seen.add(tex_path)
        content = _read_text_file(tex_path)
        if not content:
            return ""
        content = _strip_tex_comments(content)
        return _expand_tex_inputs(content, tex_path.parent, seen, depth + 1)

    stripped = _strip_tex_comments(text)
    return _INPUT_PATTERN.sub(repl, stripped)


def _strip_tex_preamble(text: str) -> str:
    begin = text.find("\\begin{document}")
    if begin != -1:
        text = text[begin + len("\\begin{document}") :]
    end = text.find("\\end{document}")
    if end != -1:
        text = text[:end]
    return text


def _latex_to_text_basic(text: str) -> str:
    text = _strip_tex_preamble(text)

    drop_envs = [
        "figure", "table", "equation", "align", "align*", "eqnarray",
        "algorithm", "algorithmic", "lstlisting", "verbatim",
        "tikzpicture", "thebibliography", "appendix",
    ]
    for env in drop_envs:
        env_pat = re.escape(env)
        text = re.sub(rf"\\begin\{{{env_pat}\}}.*?\\end\{{{env_pat}\}}", " ", text, flags=re.S)

    text = re.sub(r"\$\$.*?\$\$", " ", text, flags=re.S)
    text = re.sub(r"\$[^$]*\$", " ", text)
    text = re.sub(r"\\\[.*?\\\]", " ", text, flags=re.S)
    text = re.sub(r"\\\(.*?\\\)", " ", text, flags=re.S)

    text = re.sub(r"\\cite[a-zA-Z]*\*?(?:\[[^\]]*\])?\{[^}]*\}", " ", text)
    text = re.sub(r"\\ref\{[^}]*\}", " ", text)
    text = re.sub(r"\\label\{[^}]*\}", " ", text)
    text = re.sub(r"\\url\{[^}]*\}", " ", text)

    for _ in range(3):
        text = re.sub(r"\\[a-zA-Z@]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z@]+\*?(?:\[[^\]]*\])?", " ", text)

    text = text.replace("~", " ")
    text = text.replace("{", " ").replace("}", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _get_arxiv_source_text(paper: dict, max_tokens: int) -> Optional[str]:
    if not config.USE_ARXIV_SOURCE:
        return None
    arxiv_id = paper.get("arxiv_id")
    if not arxiv_id:
        return None

    cache_dir = config.LOGS_DIR / "source_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    global _SOURCE_CACHE_CLEANED
    if not _SOURCE_CACHE_CLEANED:
        _cleanup_source_cache(cache_dir, config.ARXIV_SOURCE_TTL_DAYS)
        _SOURCE_CACHE_CLEANED = True

    text_cache = cache_dir / f"{arxiv_id}.source.txt"
    if text_cache.exists():
        cached = _read_text_file(text_cache).strip()
        if cached:
            return _trim_text_to_max_tokens(cached, max_tokens)

    archive_path = _download_arxiv_source_archive(arxiv_id)
    if not archive_path:
        return None

    extract_dir = cache_dir / arxiv_id
    has_tex = extract_dir.exists() and any(extract_dir.rglob("*.tex"))
    if not has_tex:
        if extract_dir.exists():
            shutil.rmtree(extract_dir, ignore_errors=True)
        if not _safe_extract_tar(archive_path, extract_dir):
            # retry once in case of truncated download
            try:
                archive_path.unlink(missing_ok=True)
            except Exception:
                pass
            archive_path = _download_arxiv_source_archive(arxiv_id)
            if not archive_path or not _safe_extract_tar(archive_path, extract_dir):
                return None

    tex_paths = [p for p in extract_dir.rglob("*.tex") if p.is_file()]
    if not tex_paths:
        return None

    main_path = _select_main_tex(tex_paths)
    if not main_path:
        return None

    main_text = _read_text_file(main_path)
    if not main_text:
        return None

    expanded = _expand_tex_inputs(main_text, main_path.parent, {main_path})
    expanded = _strip_tex_preamble(expanded)
    if LatexNodes2Text is not None:
        try:
            plain = LatexNodes2Text().latex_to_text(expanded)
        except Exception:
            plain = _latex_to_text_basic(expanded)
    else:
        plain = _latex_to_text_basic(expanded)

    plain = _trim_text_to_max_tokens(plain, max_tokens)
    if plain:
        try:
            text_cache.write_text(plain, encoding="utf-8")
        except Exception:
            pass
        _prune_source_artifacts(cache_dir, arxiv_id)
    return plain or None


def _get_body_text_for_paper(paper: dict) -> Optional[str]:
    body_text = None
    if config.USE_PDF_FULLTEXT:
        pdf_path = _download_pdf_to_cache(paper)
        if pdf_path:
            body_text = _extract_pdf_body_text(
                pdf_path,
                max_body_pages=max(1, config.PDF_BODY_MAX_PAGES),
                max_tokens=max(100, config.PDF_BODY_MAX_TOKENS),
            )

    min_chars = max(200, config.ARXIV_SOURCE_MIN_CHARS)
    if config.USE_ARXIV_SOURCE and (not body_text or len(body_text) < min_chars):
        logger.info(f"正文不足，尝试源码抽取: {paper.get('arxiv_id')}")
        source_text = _get_arxiv_source_text(paper, max_tokens=max(100, config.PDF_BODY_MAX_TOKENS))
        if source_text and (not body_text or len(source_text) > len(body_text)):
            body_text = source_text

    return body_text


def analyze_paper(paper: dict, template: List[Dict[str, str]] = None) -> dict:
    """使用 LLM 分析单篇论文（支持动态模板）"""
    logger.info(f"正在分析: {paper['arxiv_id']} - {paper['title_en'][:50]}...")

    if template is None:
        template = load_template()

    cached = load_analysis_cache(paper["arxiv_id"])
    if cached:
        logger.info(f"命中缓存，跳过分析: {paper['arxiv_id']}")
        merged = {**paper, **cached}
        merged["cached_analysis"] = True
        return merged

    # 使用动态 Prompt
    body_text = _get_body_text_for_paper(paper)
    if body_text:
        logger.info(f"正文提取完成: {paper['arxiv_id']}")
    else:
        logger.info(f"正文提取失败或为空: {paper['arxiv_id']}")

    prompt = build_analysis_prompt(
        title=paper["title_en"],
        abstract=paper["abstract"],
        template=template,
        body_text=body_text,
    )

    response = call_llm(prompt)
    analysis = parse_llm_response(response)

    if analysis:
        # 合并原始信息和分析结果
        paper.update(analysis)
        logger.info(f"分析完成: 评分 {analysis.get('score', 'N/A')}/10")
    else:
        # 分析失败，使用默认值
        paper["title_cn"] = paper["title_en"]
        paper["score"] = 0
        paper["tags"] = []
        paper["analysis"] = {item["key"]: "分析失败" for item in template}
        logger.warning(f"分析失败: {paper['arxiv_id']}")

    # 保存到历史记录
    save_to_history(paper["arxiv_id"], "analyzed")
    save_analysis_cache(paper)

    return paper

def analyze_papers(
    papers: list[dict],
    delay: float = 2.0,
    progress_cb: Optional[callable] = None,
    template: List[Dict[str, str]] = None,
    cancel_cb: Optional[callable] = None,
) -> list[dict]:
    """批量分析论文"""
    analyzed = []
    total = len(papers)

    # 提前加载一次模板，避免循环中重复加载
    if template is None:
        template = load_template()

    for i, paper in enumerate(papers, 1):
        if cancel_cb and cancel_cb():
            logger.info("分析取消请求已收到，终止分析")
            break
        logger.info(f"进度: {i}/{total}")
        analyzed_paper = analyze_paper(paper, template=template)
        analyzed.append(analyzed_paper)
        if progress_cb:
            progress_cb(i, total)

        # 避免 API 限流
        if i < total and (not cancel_cb or not cancel_cb()):
            time.sleep(delay)

    return analyzed


# ============================================================ 
# 简报生成
# ============================================================ 


def generate_brief(papers: list[dict], keywords: list[str]) -> str:
    """生成 Markdown 简报（使用动态模板格式化）"""
    today = datetime.now().strftime("%Y-%m-%d")

    # 按评分排序
    papers_sorted = sorted(papers, key=lambda x: x.get("score", 0), reverse=True)

    # 加载模板（用于格式化顺序）
    template = load_template()

    # 生成头部
    content = BRIEF_HEADER_TEMPLATE.format(
        date=today,
        keywords=", ".join(keywords),
        count=len(papers),
    )

    # 分区：高分 vs 低分
    high_score = [p for p in papers_sorted if p.get("score", 0) >= SCORE_THRESHOLD]
    low_score = [p for p in papers_sorted if p.get("score", 0) < SCORE_THRESHOLD]

    if high_score:
        content += "# 推荐阅读\n\n"
        for paper in high_score:
            content += format_paper_brief(paper, template)

    if low_score:
        content += "\n# 其他论文\n\n"
        for paper in low_score:
            content += format_paper_brief(paper, template)

    return content

def save_brief(content: str) -> Path:
    """保存简报到 _inbox"""
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{today}-Daily-Brief.md"
    filepath = INBOX_DIR / filename

    # 如果文件已存在，添加序号
    counter = 1
    while filepath.exists():
        filename = f"{today}-Daily-Brief-{counter}.md"
        filepath = INBOX_DIR / filename
        counter += 1

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"简报已保存: {filepath}")
    return filepath


# ============================================================ 
# 主函数
# ============================================================ 


def main():
    parser = argparse.ArgumentParser(description="ArXiv 学术简报生成器")
    parser.add_argument(
        "-q",
        "--queries",
        nargs="+",
        default=DEFAULT_SEARCH_QUERIES,
        help="搜索关键词列表",
    )
    parser.add_argument(
        "-n",
        "--max-results",
        type=int,
        default=MAX_TOTAL_RESULTS,
        help="最大抓取论文数",
    )
    parser.add_argument(
        "--no-analyze",
        action="store_true",
        help="跳过 LLM 分析（仅抓取）",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="LLM 调用间隔（秒）",
    )
    parser.add_argument(
        "--date-from",
        type=_parse_date_arg,
        help="开始日期（YYYY-MM-DD）",
    )
    parser.add_argument(
        "--date-to",
        type=_parse_date_arg,
        help="结束日期（YYYY-MM-DD）",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("ArXiv 学术简报生成器")
    print("=" * 60)

    # 1. 抓取论文
    papers = fetch_arxiv_papers(
        queries=args.queries,
        max_total=args.max_results,
        date_from=args.date_from,
        date_to=args.date_to,
    )

    if not papers:
        print("未找到新论文，退出。")
        return

    print(f"\n找到 {len(papers)} 篇新论文")

    # 2. LLM 分析
    if not args.no_analyze:
        print("\n开始 LLM 分析...")
        papers = analyze_papers(papers, delay=args.delay)
    else:
        print("\n跳过 LLM 分析")
        # 填充默认值
        template = load_template()
        for paper in papers:
            paper["title_cn"] = paper["title_en"]
            paper["score"] = 5
            paper["tags"] = []
            paper["analysis"] = {item["key"]: "（未分析）" for item in template}

    # 3. 生成简报
    print("\n生成简报...")
    brief_content = generate_brief(papers, args.queries)
    filepath = save_brief(brief_content)

    print("\n" + "=" * 60)
    print(f"简报已生成: {filepath}")
    print("=" * 60)
    print("\n下一步:")
    print(f"1. 打开 {filepath}")
    print("2. 将感兴趣的论文从 [ ] 改为 [x]")
    print("3. 运行 python archivist.py 同步到 Zotero")


if __name__ == "__main__":
    main()
