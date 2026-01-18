import json
from pathlib import Path
from typing import List, Dict

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

def load_template() -> List[Dict[str, str]]:
    """加载分析模板，如果不存在则创建默认值"""
    if not CONFIG_FILE.exists():
        save_template(DEFAULT_TEMPLATE)
        return DEFAULT_TEMPLATE
    
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("analysis_template", DEFAULT_TEMPLATE)
    except Exception:
        return DEFAULT_TEMPLATE

def save_template(template: List[Dict[str, str]]):
    """保存分析模板"""
    data = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            pass
    
    data["analysis_template"] = template
    
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
