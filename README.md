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
- **🔗 Source Parsing**: Supports downloading and parsing ArXiv LaTeX source for more accurate full-text analysis.
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

## 🚀 Quick Start Guide

Follow these steps to deploy and start using the system from scratch.

### 1. Environment Setup
Create and activate a virtual environment (recommended):
```bash
conda create -n daily_report python=3.10
conda activate daily_report
```

### 2. Install Core Dependencies
Install the required Python backend libraries:
```bash
pip install -r requirements.txt
```

### 3. Install Frontend Dependencies
Navigate to the UI directory and install Node.js dependencies:
```bash
cd ui
npm install
cd ..
```

### 4. Start the Service
Run the startup script from the root directory to launch both the backend API and the frontend interface:
```bash
python app.py
```
> Once started, the browser should open automatically, or visit: `http://localhost:3000`

### 5. Configuration
Go to the **Settings** page and fill in your LLM API Key (e.g., OpenAI, Gemini) and Zotero configuration.

![Configuration Page](figure/configreport.png)

### 6. Start Analysis
Return to the **Fetch** page (Intelligence Gathering), enter keywords for papers you are interested in (e.g., `LLM`, `Agent`), and click **Start Fetch Task**. The system will automatically search, download, and analyze papers with AI.

### 7. Archive to Zotero
After analysis, go to the **Briefs** page (Reading Room). Review the generated brief, check the boxes for papers you value, and click the **Sync to Zotero** button at the top. The system will sync metadata, PDFs, and notes to your Zotero library.

![Briefing Page](figure/dailyreportexp.png)

---

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

## 📄 License

MIT © 2024