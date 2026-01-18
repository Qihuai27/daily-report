# 📑 Academic Briefing & Knowledge Flow System

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Node](https://img.shields.io/badge/Node-18+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React-61DAFB.svg)](https://reactjs.org/)

[**中文说明**](README_CN.md) | [Report Bug](https://github.com/yourusername/daily-report/issues) | [Request Feature](https://github.com/yourusername/daily-report/issues)

</div>

---

**Academic Briefing & Knowledge Flow System** is an end-to-end pipeline that automatically fetches recent arXiv papers, analyzes them using advanced LLMs, and seamlessly transforms selected insights into a personal knowledge base (PDFs + notes + Zotero).

## ✨ Features

- **🔍 Smart Fetching**: Automatically retrieves recent arXiv papers based on your custom keyword queries.
- **🧹 Deduplication**: Intelligent filtering via a local history log to ensure fresh content.
- **🤖 AI Analysis**: Utilizes LLMs to generate structured, insightful daily briefings.
- **✅ Curated Archiving**: Review briefs and simply mark items to select them for your permanent collection.
- **🔗 Seamless Sync**: Automatically syncs selected papers to Zotero, downloads PDFs, and creates Astro note stubs.
- **🖥️ Full Stack UI**: Includes a robust FastAPI backend and a modern Vite/React UI with a built-in scheduler.

## 🏗️ Architecture

The system follows a streamlined flow from data ingestion to knowledge persistence:

```mermaid
graph LR
    A[ArXiv API] --> B(Reporter)
    B --> C{_inbox/Daily-Brief}
    C -->|Mark [x]| D(Archivist)
    D --> E[Zotero Items]
    D --> F[PDFs public/papers/]
    D --> G[Notes content/blog/]
```

*(Text-based fallback if mermaid is not supported)*
```text
ArXiv API ──> Reporter ──> _inbox/YYYY-MM-DD-Daily-Brief.md
                                   │
                                   │  (mark [ ] -> [x])
                                   ▼
                              Archivist
                                   │
                                   ├── Zotero items
                                   ├── PDFs (public/papers/)
                                   └── Notes (content/blog/)
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Node.js 18+ (for UI)

### ⚡ Minimal Setup (CLI Only)

If you only want to use the command-line tools:

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# (Edit .env with your API keys)

# 3. Run the reporter
python src/reporter.py
```

### 📦 Full Installation (CLI + UI)

#### 1. Install Dependencies
```bash
# Backend
pip install -r requirements.txt

# Frontend
cd ui && npm install
```

#### 2. Configure Environment
Copy the example configuration and fill in your API keys:
```bash
cp .env.example .env
```

#### 3. Run the Pipeline
```bash
# Step A: Generate Briefing
python src/reporter.py

# Step B: Review & Archive
# Open _inbox/YYYY-MM-DD-Daily-Brief.md and mark interesting papers with [x]
python src/archivist.py
```

#### 4. Launch Full Application
Run the unified server (Backend + Frontend):
```bash
python app.py
```
> **Access:**
> - Backend: `http://localhost:8000`
> - UI: `http://localhost:3000`

## ⚙️ Configuration

All settings are managed via environment variables (loaded from `.env`).

### 🧠 LLM Providers
Set `LLM_PROVIDER` to one of: `openai`, `anthropic`, `gemini`, `ollama`.

| Provider | Required Variables |
| :--- | :--- |
| **OpenAI** | `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` |
| **Anthropic** | `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL` |
| **Gemini** | `GEMINI_API_KEY`, `GEMINI_BASE_URL`, `GEMINI_MODEL` |
| **Ollama** | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` |

### 📚 Zotero (Optional)

| Variable | Description |
| :--- | :--- |
| `ZOTERO_API_KEY` | Your Zotero API key |
| `ZOTERO_USER_ID` | Your Zotero User ID |
| `ZOTERO_LIBRARY_TYPE` | e.g., `user` or `group` |
| `ZOTERO_DEFAULT_COLLECTION` | Collection Key to save papers to |

### ⏰ Daily Scheduler (Optional)

| Variable | Description |
| :--- | :--- |
| `DAILY_ENABLED` | `true` or `false` |
| `DAILY_HOUR` / `DAILY_MINUTE` | Time to run the job |
| `DAILY_QUERIES` | List of search queries |
| `DAILY_MAX_RESULTS` | Max papers per fetch |

### 📄 PDF Parsing (Optional)
Controls how the system reads and processes PDF content.
- `USE_PDF_FULLTEXT`, `PDF_BODY_MAX_PAGES`, `PDF_BODY_MAX_TOKENS`
- `PDF_CACHE_TTL_DAYS`
- `USE_ARXIV_SOURCE`

## 🎨 Prompt Customization

You can tailor the AI analysis to your needs:
- **`prompts/`**: Contains system prompts and templates.
- **`user_config.json`**: Controls specific analysis sections for each paper.

## 📂 Project Structure

```text
.
├── src/                 # 🐍 Python backend (reporter/archivist/server)
├── ui/                  # ⚛️ Vite + React frontend
├── prompts/             # 📝 LLM prompt templates
├── _inbox/              # 📥 Generated Daily Briefs
├── _logs/               # 🪵 Logs & History
├── public/papers/       # 📄 Downloaded PDFs
└── content/blog/        # 📓 Generated Note Stubs
```

## 🛠️ Development

```bash
# Run FastAPI Backend independently
python src/server.py

# Run Frontend Dev Server
cd ui && npm run dev

# Lint & Build Frontend
cd ui && npm run lint
cd ui && npm run build
```

## 📄 License

MIT © 2024