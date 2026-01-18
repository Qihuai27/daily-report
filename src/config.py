"""
学术简报与知识流转系统 - 配置文件

优先读取环境变量，未设置时使用下方默认值
"""
import os
from pathlib import Path

try:
    from dotenv import dotenv_values
except Exception:
    dotenv_values = None

# ============================================================
# 路径配置
# ============================================================

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 尽量从 .env 补齐缺失/空值环境变量（不覆盖已有非空值）
if dotenv_values:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for key, value in dotenv_values(env_path).items():
            if value is None:
                continue
            if os.getenv(key) in (None, ""):
                os.environ[key] = value

# 各子目录
INBOX_DIR = PROJECT_ROOT / "_inbox"
LOGS_DIR = PROJECT_ROOT / "_logs"
PAPERS_DIR = PROJECT_ROOT / "public" / "papers"
BLOG_DIR = PROJECT_ROOT / "content" / "blog"
ARCHIVE_ROOT_DIR = Path(os.getenv("ARCHIVE_ROOT_DIR", Path.home() / "daily-report" / "arxiv"))
ANALYSIS_CACHE_DIR = LOGS_DIR / "analysis_cache"

# 历史记录文件
HISTORY_FILE = LOGS_DIR / "history.jsonl"

# 确保目录存在
for dir_path in [INBOX_DIR, LOGS_DIR, PAPERS_DIR, BLOG_DIR, ARCHIVE_ROOT_DIR, ANALYSIS_CACHE_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ============================================================
# LLM API 配置
# ============================================================

# 选择 LLM 后端: "openai", "anthropic", "gemini" (或 "ollama" 兼容 openai 协议)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")

# ---------- OpenAI (及兼容协议如 DeepSeek, Moonshot) ----------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# ---------- Anthropic (Claude) ----------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")

# ---------- Gemini (Google) ----------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Gemini 通常不需要 Base URL，除非使用代理
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "") 
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

# ---------- Ollama (本地) ----------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# ============================================================
# ArXiv 配置
# ============================================================

# 默认搜索关键词（可在命令行覆盖）
DEFAULT_SEARCH_QUERIES = [
    "LLM",
    "large language model",
    "retrieval augmented generation",
    "RAG",
    "agent",
]

# 每个查询抓取的最大论文数
MAX_RESULTS_PER_QUERY = 10

# 总共抓取的最大论文数
MAX_TOTAL_RESULTS = 30

# 排序方式: relevance, lastUpdatedDate, submittedDate
SORT_BY = "submittedDate"

# ============================================================
# 每日定时任务配置 (从 env 读取)
# ============================================================
DAILY_ENABLED = os.getenv("DAILY_ENABLED", "true").lower() == "true"
DAILY_HOUR = int(os.getenv("DAILY_HOUR", "8"))
DAILY_MINUTE = int(os.getenv("DAILY_MINUTE", "0"))
DAILY_QUERIES = os.getenv("DAILY_QUERIES", ",".join(DEFAULT_SEARCH_QUERIES)).split(",")
DAILY_MAX_RESULTS = int(os.getenv("DAILY_MAX_RESULTS", str(MAX_TOTAL_RESULTS)))
DAILY_USE_LLM = os.getenv("DAILY_USE_LLM", "true").lower() == "true"

# ============================================================
# Zotero 配置 (可选，不用 Zotero 可留空)
# ============================================================

ZOTERO_API_KEY = os.getenv("ZOTERO_API_KEY", "")
ZOTERO_USER_ID = os.getenv("ZOTERO_USER_ID", "")
ZOTERO_LIBRARY_TYPE = os.getenv("ZOTERO_LIBRARY_TYPE", "user")
ZOTERO_DEFAULT_COLLECTION = os.getenv("ZOTERO_DEFAULT_COLLECTION", "ArXiv Daily")

# ============================================================
# 简报生成配置
# ============================================================

INCLUDE_PDF_PREVIEW = True
SCORE_THRESHOLD = 6
AUTO_DOWNLOAD_PDF = False

# ============================================================
# PDF 正文解析配置
# ============================================================

USE_PDF_FULLTEXT = os.getenv("USE_PDF_FULLTEXT", "true").lower() == "true"
PDF_BODY_MAX_PAGES = int(os.getenv("PDF_BODY_MAX_PAGES", "15"))
PDF_BODY_MAX_TOKENS = int(os.getenv("PDF_BODY_MAX_TOKENS", "10000"))
PDF_CACHE_TTL_DAYS = int(os.getenv("PDF_CACHE_TTL_DAYS", "30"))
USE_ARXIV_SOURCE = os.getenv("USE_ARXIV_SOURCE", "true").lower() == "true"
ARXIV_SOURCE_MIN_CHARS = int(os.getenv("ARXIV_SOURCE_MIN_CHARS", "2000"))
ARXIV_SOURCE_MAX_MB = int(os.getenv("ARXIV_SOURCE_MAX_MB", "30"))
ARXIV_SOURCE_TTL_DAYS = int(os.getenv("ARXIV_SOURCE_TTL_DAYS", "30"))
ARXIV_SOURCE_KEEP_ARCHIVE = os.getenv("ARXIV_SOURCE_KEEP_ARCHIVE", "false").lower() == "true"

# ============================================================
# 日志配置
# ============================================================

import logging

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS_DIR / "system.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger("knowledge-system")
