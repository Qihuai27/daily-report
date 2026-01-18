import json
from pathlib import Path
from typing import List, Dict, Any, Optional

# 配置文件路径
CONFIG_FILE = Path(__file__).parent.parent / "user_config.json"

# 默认分析模板（对应你的需求：摘要、形式化、解决方法）
DEFAULT_TEMPLATE = [
    {
        "key": "summary",
        "label": "核心摘要",
        "prompt": "请用中文简明扼要地总结这篇论文的核心贡献和创新点（100字以内）。"
    },
    {
        "key": "formulation",
        "label": "问题形式化",
        "prompt": "请提取文中对问题的形式化定义，包括 Input, Output, Objective, Constraints 等，使用 Markdown 列表格式列出。"
    },
    {
        "key": "method",
        "label": "解决方法",
        "prompt": "请概括文章提出的核心解决方法（Methodology），简述其关键步骤或算法原理。"
    }
]

DEFAULT_KEYWORD_TEMPLATES = [
    {
        "id": "all_fields_and",
        "label": "全文匹配（AND）",
        "desc": "每个关键词作为短语，全文范围内同时出现",
    },
    {
        "id": "title_abs_and",
        "label": "标题/摘要（AND）",
        "desc": "每个关键词作为短语，标题或摘要同时出现",
    },
    {
        "id": "title_and",
        "label": "仅标题（AND）",
        "desc": "每个关键词作为短语，标题同时出现",
    },
    {
        "id": "abs_and",
        "label": "仅摘要（AND）",
        "desc": "每个关键词作为短语，摘要同时出现",
    },
]

DEFAULT_KEYWORD_TEMPLATE_ID = "title_abs_and"

KEYWORD_LIBRARY_KEY = "keyword_library"
KEYWORD_LAST_QUERIES_KEY = "keyword_last_queries"
KEYWORD_TEMPLATE_ID_KEY = "keyword_template_id"


def _load_config() -> Dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_config(data: Dict[str, Any]) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_template() -> List[Dict[str, str]]:
    """加载分析模板，如果不存在则创建默认值"""
    data = _load_config()
    template = data.get("analysis_template")
    if not template:
        save_template(DEFAULT_TEMPLATE)
        return DEFAULT_TEMPLATE
    return template

def save_template(template: List[Dict[str, str]]):
    """保存分析模板"""
    data = _load_config()
    data["analysis_template"] = template
    _save_config(data)


def get_keyword_templates() -> List[Dict[str, str]]:
    return DEFAULT_KEYWORD_TEMPLATES


def load_keyword_library() -> List[str]:
    data = _load_config()
    library = data.get(KEYWORD_LIBRARY_KEY, [])
    return [kw for kw in library if isinstance(kw, str) and kw.strip()]


def save_keyword_library(library: List[str]) -> None:
    data = _load_config()
    deduped = []
    for kw in library:
        if isinstance(kw, str):
            text = kw.strip()
            if text and text not in deduped:
                deduped.append(text)
    data[KEYWORD_LIBRARY_KEY] = deduped
    _save_config(data)


def load_last_queries() -> List[str]:
    data = _load_config()
    queries = data.get(KEYWORD_LAST_QUERIES_KEY, [])
    return [kw for kw in queries if isinstance(kw, str) and kw.strip()]


def save_last_queries(queries: List[str]) -> None:
    data = _load_config()
    deduped = []
    for kw in queries:
        if isinstance(kw, str):
            text = kw.strip()
            if text and text not in deduped:
                deduped.append(text)
    data[KEYWORD_LAST_QUERIES_KEY] = deduped
    _save_config(data)


def load_keyword_template_id() -> str:
    data = _load_config()
    template_id = data.get(KEYWORD_TEMPLATE_ID_KEY, DEFAULT_KEYWORD_TEMPLATE_ID)
    if not isinstance(template_id, str) or not template_id.strip():
        return DEFAULT_KEYWORD_TEMPLATE_ID
    return template_id


def save_keyword_template_id(template_id: Optional[str]) -> None:
    data = _load_config()
    if template_id:
        data[KEYWORD_TEMPLATE_ID_KEY] = template_id
    else:
        data[KEYWORD_TEMPLATE_ID_KEY] = DEFAULT_KEYWORD_TEMPLATE_ID
    _save_config(data)
