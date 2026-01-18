# 📑 学术简报与知识流转系统 (Academic Briefing System)

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Node](https://img.shields.io/badge/Node-18+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React-61DAFB.svg)](https://reactjs.org/)

[**English Documentation**](README.md) | [提交 Bug](https://github.com/yourusername/daily-report/issues) | [功能建议](https://github.com/yourusername/daily-report/issues)

</div>

---

**学术简报与知识流转系统** 是一个端到端的自动化流水线，旨在帮助研究人员高效获取知识。它能自动抓取最新的 arXiv 论文，利用先进的 LLM 进行深度分析，并将精选内容无缝沉淀为个人知识库（PDF + 笔记 + Zotero 条目）。

## ✨ 主要功能

- **🔍 智能抓取**：根据自定义关键词查询，自动获取最新的 arXiv 论文。
- **🧹 智能去重**：通过本地历史记录过滤，确保内容不重复。
- **🤖 AI 深度分析**：利用 LLM 生成结构化、有洞察力的每日简报。
- **✅ 精选归档**：在简报中审阅并简单勾选，即可将论文加入永久收藏。
- **🔗 无缝同步**：自动同步条目到 Zotero，下载 PDF 文件，并生成 Astro 笔记存根。
- **🖥️ 全栈交互**：内置强大的 FastAPI 后端与现代化的 Vite/React 前端界面，支持可视化调度。

## 🏗️ 系统架构

数据从获取到持久化的完整流转过程：

```mermaid
graph LR
    A[ArXiv API] --> B(Reporter)
    B --> C{_inbox/Daily-Brief}
    C -->|Mark [x]| D(Archivist)
    D --> E[Zotero Items]
    D --> F[PDFs public/papers/]
    D --> G[Notes content/blog/]
```

*(备用文本视图)*
```text
ArXiv API ──> Reporter ──> _inbox/YYYY-MM-DD-Daily-Brief.md
                                   │
                                   │  (把 [ ] 改成 [x])
                                   ▼
                              Archivist
                                   │
                                   ├── Zotero 条目
                                   ├── PDFs (public/papers/)
                                   └── 笔记 (content/blog/)
```

## 🚀 快速开始

### 前置要求
- Python 3.8+
- Node.js 18+ (用于前端 UI)

### ⚡ 极简运行 (仅命令行)

如果你只需要使用命令行工具：

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 配置环境
cp .env.example .env
# (编辑 .env 填入你的 API Key)

# 3. 运行简报生成器
python src/reporter.py
```

### 📦 完整安装 (CLI + UI)

#### 1. 安装依赖
```bash
# 后端依赖
pip install -r requirements.txt

# 前端依赖
cd ui && npm install
```

#### 2. 配置环境
复制示例配置并填写 Key：
```bash
cp .env.example .env
```

#### 3. 运行工作流
```bash
# 步骤 A: 生成简报
python src/reporter.py

# 步骤 B: 审阅与归档
# 打开 _inbox/YYYY-MM-DD-Daily-Brief.md 并勾选感兴趣的论文 [x]
python src/archivist.py
```

#### 4. 启动完整应用
启动统一服务（后端 + 前端）：
```bash
python app.py
```
> **访问地址：**
> - 后端 API: `http://localhost:8000`
> - 前端 UI: `http://localhost:3000`

## ⚙️ 配置说明

系统所有配置均通过环境变量管理（自动加载 `.env`）。

### 🧠 LLM 提供商配置
设置 `LLM_PROVIDER` 为以下之一：`openai`, `anthropic`, `gemini`, `ollama`。

| 提供商 (Provider) | 必需变量 |
| :--- | :--- |
| **OpenAI** | `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` |
| **Anthropic** | `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL` |
| **Gemini** | `GEMINI_API_KEY`, `GEMINI_BASE_URL`, `GEMINI_MODEL` |
| **Ollama** | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` |

### 📚 Zotero (可选)

| 变量名 | 说明 |
| :--- | :--- |
| `ZOTERO_API_KEY` | 你的 Zotero API Key |
| `ZOTERO_USER_ID` | 你的 Zotero User ID |
| `ZOTERO_LIBRARY_TYPE` | 例如 `user` (个人) 或 `group` (群组) |
| `ZOTERO_DEFAULT_COLLECTION` | 论文保存的目标 Collection Key |

### ⏰ 定时任务 (可选)

| 变量名 | 说明 |
| :--- | :--- |
| `DAILY_ENABLED` | `true` 开启或 `false` 关闭 |
| `DAILY_HOUR` / `DAILY_MINUTE` | 每日运行时间 |
| `DAILY_QUERIES` | 搜索查询关键词列表 |
| `DAILY_MAX_RESULTS` | 每次获取的最大论文数 |

### 📄 PDF 解析 (可选)
控制系统如何读取和处理 PDF 内容：
- `USE_PDF_FULLTEXT`, `PDF_BODY_MAX_PAGES`, `PDF_BODY_MAX_TOKENS`
- `PDF_CACHE_TTL_DAYS`
- `USE_ARXIV_SOURCE`

## 🎨 Prompt 定制

你可以根据需求定制 AI 分析逻辑：
- **`prompts/`**: 包含系统提示词和分析模板。
- **`user_config.json`**: 自定义每篇论文分析输出的具体段落。

## 📂 目录结构

```text
.
├── src/                 # 🐍 Python 后端 (reporter/archivist/server)
├── ui/                  # ⚛️ Vite + React 前端
├── prompts/             # 📝 LLM Prompt 模板
├── _inbox/              # 📥 生成的每日简报
├── _logs/               # 🪵 日志与历史记录
├── public/papers/       # 📄 下载的 PDF 文件
└── content/blog/        # 📓 生成的笔记存根
```

## 🛠️ 开发指南

```bash
# 独立运行 FastAPI 后端
python src/server.py

# 运行前端开发服务器
cd ui && npm run dev

# 前端代码检查与构建
cd ui && npm run lint
cd ui && npm run build
```

## 📄 License

MIT © 2024