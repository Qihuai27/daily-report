# Repository Guidelines

## Project Structure & Module Organization
- `src/`: Python backend scripts (reporter/archivist/server) and configuration.
- `ui/`: Vite + React (TypeScript) frontend.
- `prompts/`: LLM prompt templates.
- `_inbox/`: Daily brief markdown outputs.
- `_logs/`: Runtime logs and history (`system.log`, `history.jsonl`).
- `public/papers/` and `content/blog/`: Astro-facing PDFs and note stubs.

## Build, Test, and Development Commands
- `pip install -r requirements.txt`: Install Python dependencies.
- `python src/reporter.py`: Fetch and analyze ArXiv papers into `_inbox/`.
- `python src/archivist.py`: Sync selected briefs to Zotero/PDF/notes.
- `python src/server.py`: Start FastAPI backend (API + scheduler).
- `python start_system.py`: Start backend + frontend together.
- `cd ui && npm run dev`: Run Vite dev server.
- `cd ui && npm run build`: Type-check and build frontend.
- `cd ui && npm run lint`: Run ESLint on frontend.

## Coding Style & Naming Conventions
- Python: 4-space indentation, PEP 8-ish layout; prefer `snake_case` for files/functions.
- TypeScript/React: `PascalCase` for components, `camelCase` for variables/functions.
- Keep prompts modular in `prompts/` and avoid duplicating templates.

## Testing Guidelines
- No automated test suite is present. Use smoke tests instead:
  - Run `python src/reporter.py` and verify `_inbox/YYYY-MM-DD-Daily-Brief.md`.
  - Run `python src/archivist.py` and confirm outputs in `public/papers/` and `content/blog/`.
  - Run backend + UI to validate the end-to-end flow.
- Frontend linting is the current gate: `cd ui && npm run lint`.

## Commit & Pull Request Guidelines
- No Git history is available in this repo. If you start one, use concise imperative subjects (e.g., “Add daily scheduler”) and optional scopes (`src:`, `ui:`).
- PRs should include a short summary, test evidence (commands + results), and screenshots for UI changes.

## Security & Configuration Tips
- Store API keys in environment variables or `.env`; never commit secrets.
- Key settings live in `src/config.py` and `user_config.json`. Update both intentionally and document changes.
- Check `_logs/system.log` and `_logs/server.log` when debugging failures.
