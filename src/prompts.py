"""
学术简报与知识流转系统 - LLM Prompt 模板 (动态配置版)

这里定义了用于论文解析的各种 Prompt 模板。
现在支持根据用户配置动态生成 Prompt。
"""
import json
from pathlib import Path
from typing import List, Dict, Optional

from user_config import load_template

# ============================================================ 
# 系统提示词 (固定)
# ============================================================ 

SYSTEM_PROMPT = """你是一位精通计算机科学（特别是 AI/LLM/NLP 领域）的资深学术研究员。

你的核心能力：
1. 快速抓住论文的本质创新点
2. 将模糊的问题描述抽象为精确的数学/逻辑形式化表达
3. 准确评估论文的学术价值和实用价值

你的输出必须：
- 简洁精确，避免冗长
- 包含数学符号和形式化表达（当适用时）
- 保持学术严谨性"""

# ============================================================ 
# 简报头部模板
# ============================================================ 

BRIEF_HEADER_TEMPLATE = """# ArXiv 学术简报

**日期**：{date}
**关键词**：{keywords}
**论文数量**：{count} 篇

---

> 勾选 `[ ]` 变为 `[x]` 后点击"归档"可自动同步到 Zotero

---

"""

# ============================================================ 
# 辅助函数
# ============================================================ 

def build_analysis_prompt(
    title: str,
    abstract: str,
    template: List[Dict[str, str]] = None,
    body_text: Optional[str] = None,
) -> str:
    """
    根据用户配置的模板构建动态 Prompt
    """
    if template is None:
        template = load_template()
    
    # 动态构建 JSON Schema 描述
    json_structure = {
        "title_cn": "中文标题（准确翻译）",
        "score": 7,
        "tags": ["Tag1", "Tag2"],
        "analysis": {} # 这里存放动态字段
    }
    
    # 构建分析指令部分
    analysis_instructions = []
    for item in template:
        key = item["key"]
        desc = item["prompt"]
        json_structure["analysis"][key] = desc
        analysis_instructions.append(f"- **{item['label']} ({key})**: {desc}")
    
    instruction_str = "\n".join(analysis_instructions)
    json_str = json.dumps(json_structure, indent=4, ensure_ascii=False)

    prompt = f"""请分析以下论文，并以 JSON 格式返回结构化信息。

**论文标题**：{title}

**论文摘要**：
{abstract}

"""

    if body_text:
        prompt += f"""**论文正文（PDF 抽取纯文本，已去参考文献并做长度截断）**：
{body_text}

"""

    prompt += f"""---

请根据以下要求进行深入分析：
{instruction_str}

请严格按照以下 JSON 格式输出（不要包含 Markdown 代码块，直接返回纯 JSON）：

{json_str}

评分标准 (0-10)：
- 9-10: 开创性工作，可能改变领域方向
- 7-8: 扎实的创新，有明显的技术贡献
- 5-6: 增量式改进，有一定价值
- 3-4: 工程应用或简单组合，创新有限
- 1-2: 价值存疑

标签建议：
LLM, RAG, Agent, Reasoning, Memory, Efficiency, Training, Inference, Multimodal
"""
    return prompt


def format_paper_brief(paper_data: dict, template: List[Dict[str, str]] = None) -> str:
    """
    将解析后的论文数据格式化为 Markdown (动态)
    """
    if template is None:
        template = load_template()

    # 基础信息
    title_cn = paper_data.get("title_cn", "未知标题")
    title_en = paper_data.get("title_en", "")
    arxiv_id = paper_data.get("arxiv_id", "")
    arxiv_url = paper_data.get("arxiv_url", "")
    pdf_url = paper_data.get("pdf_url", "")
    score = paper_data.get("score", "N/A")
    tags_str = " ".join([f"`#{tag}`" for tag in paper_data.get("tags", [])])

    # 头部
    md = f"## - [ ] [{title_cn}]({arxiv_url})\n"
    md += f"> **原题**：*{title_en}*\n"
    md += f"> **ArXiv ID**：`{arxiv_id}` | **评分**：**{score}**\n\n"

    # 动态分析部分
    # 注意：LLM 返回的结构可能是 flat 的，也可能是嵌套在 'analysis' 里的
    # 我们先尝试从 'analysis' 取，没有的话从根节点取
    analysis_data = paper_data.get("analysis", paper_data)
    
    for item in template:
        key = item["key"]
        label = item["label"]
        content = analysis_data.get(key, "N/A")
        
        # 特殊处理：如果内容是字典（如旧版的 formulation），格式化为列表
        if isinstance(content, dict):
            content_str = "\n"
            for k, v in content.items():
                content_str += f"- **{k}**: {v}\n"
            content = content_str.strip()
        
        md += f"### {label}\n{content}\n\n"

    # 标签
    if tags_str:
        md += f"### 标签\n{tags_str}\n\n"

    md += f"[PDF]({pdf_url}) | [ArXiv]({arxiv_url})\n\n---\n\n"
    
    return md
