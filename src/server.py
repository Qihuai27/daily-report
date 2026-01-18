import os
import sys
import json
import re
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv, set_key

# Ensure we can import modules from the same directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ============================================================ 
# Configuration & Initialization
# ============================================================ 

ENV_FILE = Path(__file__).parent.parent / ".env"
if not ENV_FILE.exists():
    ENV_FILE.touch()
load_dotenv(ENV_FILE)

# Import existing logic (after .env is loaded)
import config
import reporter
import archivist
import user_config

LOGS_DIR = config.LOGS_DIR
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS_DIR / "server.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("server")

app = FastAPI(title="Academic Brief Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================ 
# Data Models
# ============================================================ 

class ConfigUpdate(BaseModel):
    # Provider Selection
    llm_provider: Optional[str] = None
    
    # OpenAI
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = None
    
    # Anthropic
    anthropic_api_key: Optional[str] = None
    anthropic_base_url: Optional[str] = None
    anthropic_model: Optional[str] = None
    
    # Gemini
    gemini_api_key: Optional[str] = None
    gemini_base_url: Optional[str] = None
    gemini_model: Optional[str] = None

    # Ollama
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = None
    
    # Zotero
    zotero_api_key: Optional[str] = None
    zotero_user_id: Optional[str] = None
    
    # Others
    search_queries: Optional[List[str]] = None
    use_pdf_fulltext: Optional[bool] = None
    pdf_body_max_pages: Optional[int] = None
    pdf_body_max_tokens: Optional[int] = None
    pdf_cache_ttl_days: Optional[int] = None
    use_arxiv_source: Optional[bool] = None
    arxiv_source_min_chars: Optional[int] = None
    arxiv_source_max_mb: Optional[int] = None
    arxiv_source_ttl_days: Optional[int] = None
    arxiv_source_keep_archive: Optional[bool] = None

class FetchRequest(BaseModel):
    queries: List[str]
    max_results: int = 10
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    use_llm: bool = True
    query_template_id: Optional[str] = None

class ArchiveRequest(BaseModel):
    filename: str
    collection: Optional[str] = None

class ScheduleUpdate(BaseModel):
    enabled: Optional[bool] = None
    hour: Optional[int] = None
    minute: Optional[int] = None
    queries: Optional[List[str]] = None
    max_results: Optional[int] = None
    use_llm: Optional[bool] = None

class TemplateItem(BaseModel):
    key: str
    label: str
    prompt: str

class TemplateUpdate(BaseModel):
    template: List[TemplateItem]

class RenameRequest(BaseModel):
    new_name: str


class KeywordUpdate(BaseModel):
    library: Optional[List[str]] = None
    last_queries: Optional[List[str]] = None
    template_id: Optional[str] = None

# ============================================================ 
# Task Management (Unchanged)
# ============================================================ 

class TaskManager:
    def __init__(self):
        self.status = "idle"
        self.current_task = None
        self.message = "系统就绪"
        self.logs = []
        self.progress_current = 0
        self.progress_total = 0
        self.progress_stage = None
        self.cancel_requested = False
        self.cancel_reason = None

    def start(self, task_name: str):
        self.status = "busy"
        self.current_task = task_name
        self.message = f"正在执行: {task_name}"
        self.log(f"任务开始: {task_name}")
        self.progress_current = 0
        self.progress_total = 0
        self.progress_stage = None
        self.cancel_requested = False
        self.cancel_reason = None

    def update(self, message: str):
        self.message = message
        self.log(message)

    def finish(self, message: str = "任务完成"):
        self.status = "idle"
        self.current_task = None
        self.message = message
        self.log(message)
        self.progress_current = 0
        self.progress_total = 0
        self.progress_stage = None
        self.cancel_requested = False
        self.cancel_reason = None

    def error(self, error_msg: str):
        self.status = "error"
        self.message = f"错误: {error_msg}"
        self.log(f"错误: {error_msg}")
        self.current_task = None
        self.progress_current = 0
        self.progress_total = 0
        self.progress_stage = None
        self.cancel_requested = False
        self.cancel_reason = None

    def set_progress(self, current: int, total: int, stage: Optional[str] = None):
        self.progress_current = max(0, current)
        self.progress_total = max(0, total)
        if stage is not None:
            self.progress_stage = stage

    def log(self, text: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {text}")
        if len(self.logs) > 50:
            self.logs.pop(0)

    def request_cancel(self, reason: str = "用户取消") -> bool:
        if self.status != "busy":
            return False
        self.cancel_requested = True
        self.cancel_reason = reason
        self.update("正在取消任务...")
        return True

    def is_cancelled(self) -> bool:
        return self.cancel_requested

from apscheduler.schedulers.background import BackgroundScheduler

task_manager = TaskManager()
scheduler = BackgroundScheduler()

def daily_job():
    logger.info("Triggering daily automatic brief generation")
    req = FetchRequest(
        queries=config.DAILY_QUERIES,
        max_results=config.DAILY_MAX_RESULTS,
        use_llm=config.DAILY_USE_LLM,
    )
    run_fetch_task(req)

def schedule_daily_job():
    job_id = "daily_job"
    existing = scheduler.get_job(job_id)
    if existing:
        scheduler.remove_job(job_id)

    if not config.DAILY_ENABLED:
        logger.info("Daily job disabled")
        return

    scheduler.add_job(
        daily_job,
        "cron",
        hour=config.DAILY_HOUR,
        minute=config.DAILY_MINUTE,
        id=job_id,
        replace_existing=True,
    )
    logger.info(
        "Daily job scheduled at %02d:%02d", config.DAILY_HOUR, config.DAILY_MINUTE
    )

schedule_daily_job()
scheduler.start()

# ============================================================ 
# Background Tasks (Unchanged Logic)
# ============================================================ 

def run_fetch_task(req: FetchRequest):
    try:
        task_manager.start("抓取与分析")

        user_config.save_last_queries(req.queries)
        template_id = req.query_template_id or user_config.load_keyword_template_id()
        user_config.save_keyword_template_id(template_id)
        
        task_manager.update(f"正在搜索 ArXiv: {req.queries}...")
        task_manager.set_progress(0, 0, "fetching")
        papers = reporter.fetch_arxiv_papers(
            queries=req.queries,
            max_total=req.max_results,
            date_from=req.date_from,
            date_to=req.date_to,
            query_template_id=template_id,
            cancel_cb=task_manager.is_cancelled,
        )

        if task_manager.is_cancelled():
            task_manager.finish("抓取已取消")
            return
        
        if not papers:
            task_manager.finish("未找到新论文")
            return

        if req.use_llm:
            task_manager.update(f"开始 LLM 深度分析 ({len(papers)} 篇)...")
            task_manager.set_progress(0, len(papers), "analyzing")
            def _progress_cb(current: int, total: int):
                task_manager.set_progress(current, total, "analyzing")
            papers = reporter.analyze_papers(
                papers,
                delay=2.0,
                progress_cb=_progress_cb,
                template=user_config.load_template(),
                cancel_cb=task_manager.is_cancelled,
            )
        else:
            task_manager.update("跳过 LLM 分析")
            template = user_config.load_template()
            for paper in papers:
                cached = reporter.load_analysis_cache(paper["arxiv_id"])
                if cached:
                    paper.update(cached)
                    paper["cached_analysis"] = True
                    continue
                paper.setdefault("title_cn", paper["title_en"])
                paper.setdefault("innovation", "（未分析）")
                paper.setdefault("score", 5)
                paper.setdefault("tags", [])
                paper.setdefault("analysis", {item["key"]: "（未分析）" for item in template})

        if task_manager.is_cancelled():
            task_manager.finish("分析已取消")
            return

        task_manager.set_progress(len(papers), len(papers), "generating")
        task_manager.update("正在生成简报文件...")
        content = reporter.generate_brief(papers, req.queries)
        filepath = reporter.save_brief(content)
        
        task_manager.finish(f"简报已生成: {filepath.name}")

    except Exception as e:
        logger.exception("Fetch task failed")
        task_manager.error(str(e))

def run_archive_task(filename: str, collection: Optional[str] = None):
    try:
        task_manager.start("归档同步")
        filepath = config.INBOX_DIR / filename
        
        if not filepath.exists():
            raise FileNotFoundError(f"找不到文件: {filename}")

        task_manager.update("解析选中论文...")
        papers = archivist.parse_brief(filepath)
        
        if not papers:
            task_manager.finish("没有勾选任何论文")
            return

        task_manager.update(f"发现 {len(papers)} 篇待处理论文")
        
        if config.ZOTERO_API_KEY and config.ZOTERO_USER_ID:
            task_manager.update("正在同步到 Zotero...")
            collection_name = collection or config.ZOTERO_DEFAULT_COLLECTION
            archivist.sync_to_zotero(papers, collection_name)
        
        task_manager.update("正在下载 PDF 并创建笔记...")
        pdf_paths = {}
        for paper in papers:
            path = archivist.download_pdf(paper)
            public_path = archivist.ensure_public_copy(path) if path else None
            if public_path:
                pdf_paths[paper["arxiv_id"]] = public_path
            archivist.create_astro_stub(paper, public_path)
            archivist.update_history(paper["arxiv_id"], "synced")

        task_manager.finish(f"成功归档 {len(papers)} 篇论文")

    except Exception as e:
        logger.exception("Archive task failed")
        task_manager.error(str(e))

# ============================================================ 
# Config API
# ============================================================ 

@app.get("/api/config")
def get_api_config():
    return {
        "llm_provider": config.LLM_PROVIDER,
        
        "openai_model": config.OPENAI_MODEL,
        "openai_base_url": config.OPENAI_BASE_URL,
        "has_openai_key": bool(config.OPENAI_API_KEY),
        
        "anthropic_model": config.ANTHROPIC_MODEL,
        "anthropic_base_url": config.ANTHROPIC_BASE_URL,
        "has_anthropic_key": bool(config.ANTHROPIC_API_KEY),
        
        "gemini_model": config.GEMINI_MODEL,
        "gemini_base_url": config.GEMINI_BASE_URL,
        "has_gemini_key": bool(config.GEMINI_API_KEY),

        "ollama_base_url": config.OLLAMA_BASE_URL,
        "ollama_model": config.OLLAMA_MODEL,
        
        "zotero_user_id": config.ZOTERO_USER_ID,
        "zotero_collection": config.ZOTERO_DEFAULT_COLLECTION,
        "has_zotero_key": bool(config.ZOTERO_API_KEY),
        
        "search_queries": config.DEFAULT_SEARCH_QUERIES,
        "use_pdf_fulltext": config.USE_PDF_FULLTEXT,
        "pdf_body_max_pages": config.PDF_BODY_MAX_PAGES,
        "pdf_body_max_tokens": config.PDF_BODY_MAX_TOKENS,
        "pdf_cache_ttl_days": config.PDF_CACHE_TTL_DAYS,
        "use_arxiv_source": config.USE_ARXIV_SOURCE,
        "arxiv_source_min_chars": config.ARXIV_SOURCE_MIN_CHARS,
        "arxiv_source_max_mb": config.ARXIV_SOURCE_MAX_MB,
        "arxiv_source_ttl_days": config.ARXIV_SOURCE_TTL_DAYS,
        "arxiv_source_keep_archive": config.ARXIV_SOURCE_KEEP_ARCHIVE,
    }

@app.post("/api/config")
def update_api_config(updates: ConfigUpdate):
    if updates.llm_provider:
        set_key(str(ENV_FILE), "LLM_PROVIDER", updates.llm_provider)
        config.LLM_PROVIDER = updates.llm_provider

    # OpenAI
    if updates.openai_api_key is not None:
        set_key(str(ENV_FILE), "OPENAI_API_KEY", updates.openai_api_key)
        config.OPENAI_API_KEY = updates.openai_api_key
    if updates.openai_base_url is not None:
        set_key(str(ENV_FILE), "OPENAI_BASE_URL", updates.openai_base_url)
        config.OPENAI_BASE_URL = updates.openai_base_url
    if updates.openai_model is not None:
        set_key(str(ENV_FILE), "OPENAI_MODEL", updates.openai_model)
        config.OPENAI_MODEL = updates.openai_model

    # Anthropic
    if updates.anthropic_api_key is not None:
        set_key(str(ENV_FILE), "ANTHROPIC_API_KEY", updates.anthropic_api_key)
        config.ANTHROPIC_API_KEY = updates.anthropic_api_key
    if updates.anthropic_base_url is not None:
        set_key(str(ENV_FILE), "ANTHROPIC_BASE_URL", updates.anthropic_base_url)
        config.ANTHROPIC_BASE_URL = updates.anthropic_base_url
    if updates.anthropic_model is not None:
        set_key(str(ENV_FILE), "ANTHROPIC_MODEL", updates.anthropic_model)
        config.ANTHROPIC_MODEL = updates.anthropic_model

    # Gemini
    if updates.gemini_api_key is not None:
        set_key(str(ENV_FILE), "GEMINI_API_KEY", updates.gemini_api_key)
        config.GEMINI_API_KEY = updates.gemini_api_key
    if updates.gemini_base_url is not None:
        set_key(str(ENV_FILE), "GEMINI_BASE_URL", updates.gemini_base_url)
        config.GEMINI_BASE_URL = updates.gemini_base_url
    if updates.gemini_model is not None:
        set_key(str(ENV_FILE), "GEMINI_MODEL", updates.gemini_model)
        config.GEMINI_MODEL = updates.gemini_model

    # Ollama
    if updates.ollama_base_url is not None:
        set_key(str(ENV_FILE), "OLLAMA_BASE_URL", updates.ollama_base_url)
        config.OLLAMA_BASE_URL = updates.ollama_base_url
    if updates.ollama_model is not None:
        set_key(str(ENV_FILE), "OLLAMA_MODEL", updates.ollama_model)
        config.OLLAMA_MODEL = updates.ollama_model

    # Zotero
    if updates.zotero_api_key is not None:
        set_key(str(ENV_FILE), "ZOTERO_API_KEY", updates.zotero_api_key)
        config.ZOTERO_API_KEY = updates.zotero_api_key
    if updates.zotero_user_id is not None:
        set_key(str(ENV_FILE), "ZOTERO_USER_ID", updates.zotero_user_id)
        config.ZOTERO_USER_ID = updates.zotero_user_id

    # PDF Body Extraction
    if updates.use_pdf_fulltext is not None:
        set_key(str(ENV_FILE), "USE_PDF_FULLTEXT", "true" if updates.use_pdf_fulltext else "false")
        config.USE_PDF_FULLTEXT = updates.use_pdf_fulltext
    if updates.pdf_body_max_pages is not None:
        set_key(str(ENV_FILE), "PDF_BODY_MAX_PAGES", str(updates.pdf_body_max_pages))
        config.PDF_BODY_MAX_PAGES = updates.pdf_body_max_pages
    if updates.pdf_body_max_tokens is not None:
        set_key(str(ENV_FILE), "PDF_BODY_MAX_TOKENS", str(updates.pdf_body_max_tokens))
        config.PDF_BODY_MAX_TOKENS = updates.pdf_body_max_tokens
    if updates.pdf_cache_ttl_days is not None:
        set_key(str(ENV_FILE), "PDF_CACHE_TTL_DAYS", str(updates.pdf_cache_ttl_days))
        config.PDF_CACHE_TTL_DAYS = updates.pdf_cache_ttl_days
    if updates.use_arxiv_source is not None:
        set_key(str(ENV_FILE), "USE_ARXIV_SOURCE", "true" if updates.use_arxiv_source else "false")
        config.USE_ARXIV_SOURCE = updates.use_arxiv_source
    if updates.arxiv_source_min_chars is not None:
        set_key(str(ENV_FILE), "ARXIV_SOURCE_MIN_CHARS", str(updates.arxiv_source_min_chars))
        config.ARXIV_SOURCE_MIN_CHARS = updates.arxiv_source_min_chars
    if updates.arxiv_source_max_mb is not None:
        set_key(str(ENV_FILE), "ARXIV_SOURCE_MAX_MB", str(updates.arxiv_source_max_mb))
        config.ARXIV_SOURCE_MAX_MB = updates.arxiv_source_max_mb
    if updates.arxiv_source_ttl_days is not None:
        set_key(str(ENV_FILE), "ARXIV_SOURCE_TTL_DAYS", str(updates.arxiv_source_ttl_days))
        config.ARXIV_SOURCE_TTL_DAYS = updates.arxiv_source_ttl_days
    if updates.arxiv_source_keep_archive is not None:
        set_key(
            str(ENV_FILE),
            "ARXIV_SOURCE_KEEP_ARCHIVE",
            "true" if updates.arxiv_source_keep_archive else "false",
        )
        config.ARXIV_SOURCE_KEEP_ARCHIVE = updates.arxiv_source_keep_archive

    return {"status": "success"}

# ============================================================ 
# Other Endpoints (Unchanged)
# ============================================================ 

@app.get("/api/status")
def get_status():
    return {
        "status": task_manager.status,
        "task": task_manager.current_task,
        "message": task_manager.message,
        "logs": task_manager.logs,
        "progress_current": task_manager.progress_current,
        "progress_total": task_manager.progress_total,
        "progress_stage": task_manager.progress_stage,
        "cancel_requested": task_manager.cancel_requested,
    }

@app.post("/api/cancel")
def cancel_task():
    if not task_manager.request_cancel():
        raise HTTPException(status_code=400, detail="No running task")
    return {"status": "cancelling"}

@app.get("/api/briefs")
def list_briefs():
    files = sorted(list(config.INBOX_DIR.glob("*.md")), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {
            "id": f.name,
            "name": f.name,
            "date": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            "size": f.stat().st_size
        } for f in files
    ]

@app.get("/api/briefs/{filename}")
def get_brief_content(filename: str):
    filepath = config.INBOX_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    template = user_config.load_template()
    papers = []
    chunks = re.split(r"(?=## - \[)", content)
    header = chunks[0]
    
    for chunk in chunks[1:]:
        match = re.match(r"## - \[( |x)\] \[(.+?)\]\((.+?)\)", chunk)
        if match:
            arxiv_id = match.group(3).split("/")[-1]
            title_cn = match.group(2)
            
            score = 0
            score_match = re.search(r"\*\*评分\*\*：\*+(\d+)", chunk)
            if score_match: score = int(score_match.group(1))
            
            title_en = ""
            en_match = re.search(r"\*\*原题\*\*：\*(.+?)\*", chunk)
            if en_match: title_en = en_match.group(1)
            
            analysis = {}
            sections = re.split(r"\n### ", chunk)
            tags = []
            
            for section in sections:
                lines = section.split("\n", 1)
                if len(lines) < 2: continue
                
                header_line = lines[0].strip()
                content_body = lines[1].strip()
                
                if header_line == "标签":
                     tags = re.findall(r"`#(\w+)`", content_body)
                     continue
                
                matched_key = None
                for t in template:
                    if t["label"] == header_line:
                        matched_key = t["key"]
                        break
                
                if matched_key:
                    analysis[matched_key] = content_body
                elif header_line == "核心创新": 
                     analysis["innovation"] = content_body
                elif header_line == "问题形式化": 
                     analysis["formulation"] = content_body
                elif header_line == "方法概要": 
                     analysis["method"] = content_body

            papers.append({
                "id": arxiv_id,
                "title_cn": title_cn,
                "title_en": title_en,
                "url": match.group(3),
                "checked": match.group(1) == "x",
                "score": score,
                "tags": tags,
                "analysis": analysis
            })
            
    return {"header": header, "papers": papers}

@app.post("/api/briefs/{filename}/rename")
def rename_brief(filename: str, req: RenameRequest):
    filepath = config.INBOX_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    new_name = Path(req.new_name).name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not new_name.endswith(".md"):
        new_name = f"{new_name}.md"
    new_path = config.INBOX_DIR / new_name
    if new_path.exists():
        raise HTTPException(status_code=409, detail="Target already exists")
    filepath.rename(new_path)
    return {"status": "success", "name": new_path.name}

@app.delete("/api/briefs/{filename}")
def delete_brief(filename: str):
    filepath = config.INBOX_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    filepath.unlink()
    return {"status": "success"}

@app.post("/api/briefs/{filename}/check")
def toggle_check(filename: str, paper_id: str, checked: bool):
    filepath = config.INBOX_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    char = "x" if checked else " "
    pattern = rf"(## - \[)[ x](\] \[.*?\(.*?{re.escape(paper_id)}\))"
    new_content = re.sub(pattern, rf"\g<1>{char}\g<2>", content)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    return {"status": "success"}

@app.post("/api/fetch")
def start_fetch(req: FetchRequest, background_tasks: BackgroundTasks):
    if task_manager.status == "busy":
        raise HTTPException(status_code=400, detail="System busy")
    background_tasks.add_task(run_fetch_task, req)
    return {"status": "started"}

@app.post("/api/archive")
def start_archive(req: ArchiveRequest, background_tasks: BackgroundTasks):
    if task_manager.status == "busy":
        raise HTTPException(status_code=400, detail="System busy")
    background_tasks.add_task(run_archive_task, req.filename, req.collection)
    return {"status": "started"}

@app.get("/api/schedule")
def get_schedule():
    return {
        "enabled": config.DAILY_ENABLED,
        "hour": config.DAILY_HOUR,
        "minute": config.DAILY_MINUTE,
        "queries": config.DAILY_QUERIES,
        "max_results": config.DAILY_MAX_RESULTS,
        "use_llm": config.DAILY_USE_LLM,
    }

@app.post("/api/schedule")
def update_schedule(updates: ScheduleUpdate):
    if updates.enabled is not None:
        set_key(str(ENV_FILE), "DAILY_ENABLED", "true" if updates.enabled else "false")
        config.DAILY_ENABLED = updates.enabled
    if updates.hour is not None:
        set_key(str(ENV_FILE), "DAILY_HOUR", str(updates.hour))
        config.DAILY_HOUR = updates.hour
    if updates.minute is not None:
        set_key(str(ENV_FILE), "DAILY_MINUTE", str(updates.minute))
        config.DAILY_MINUTE = updates.minute
    if updates.queries is not None:
        joined = ",".join([q.strip() for q in updates.queries if q.strip()])
        set_key(str(ENV_FILE), "DAILY_QUERIES", joined)
        config.DAILY_QUERIES = [q.strip() for q in updates.queries if q.strip()]
        if not config.DAILY_QUERIES:
            config.DAILY_QUERIES = config.DEFAULT_SEARCH_QUERIES
    if updates.max_results is not None:
        set_key(str(ENV_FILE), "DAILY_MAX_RESULTS", str(updates.max_results))
        config.DAILY_MAX_RESULTS = updates.max_results
    if updates.use_llm is not None:
        set_key(str(ENV_FILE), "DAILY_USE_LLM", "true" if updates.use_llm else "false")
        config.DAILY_USE_LLM = updates.use_llm
    schedule_daily_job()
    return {"status": "success"}

@app.get("/api/template")
def get_analysis_template():
    return {"template": user_config.load_template()}

@app.post("/api/template")
def update_analysis_template(update: TemplateUpdate):
    user_config.save_template([item.dict() for item in update.template])
    return {"status": "success"}

@app.get("/api/keywords")
def get_keywords():
    return {
        "library": user_config.load_keyword_library(),
        "last_queries": user_config.load_last_queries(),
        "template_id": user_config.load_keyword_template_id(),
        "templates": user_config.get_keyword_templates(),
    }

@app.post("/api/keywords")
def update_keywords(update: KeywordUpdate):
    if update.library is not None:
        user_config.save_keyword_library(update.library)
    if update.last_queries is not None:
        user_config.save_last_queries(update.last_queries)
    if update.template_id is not None:
        user_config.save_keyword_template_id(update.template_id)
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
