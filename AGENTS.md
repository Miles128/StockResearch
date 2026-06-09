# AGENTS.md — StockResearch

AI stock research assistant (formerly InvesBao). Multi-agent LangGraph backend + React/Vite UI.

## Quick start

```bash
cd "/Users/sihai/Documents/My Projects/StockResearch"
uv sync
cp .env.example .env   # LLM keys; USE_MOCK_LLM=true for offline dev
cd web && npm install
```

**Dev (two terminals):**

```bash
# API :8000 — --app-dir src is required
uv run uvicorn stockresearch.api.app:app --reload --host 127.0.0.1 --port 8000 --app-dir src

# UI :5174
cd web && npm run dev
```

## Verification

```bash
pytest
cd web && npm run build
```

## Architecture

```
src/stockresearch/   Python package (api, agents, services, data, db)
web/src/             React UI (Chat, News, Portfolio, Risk, Settings)
tests/               pytest
```

Flow: browser `:5174` → REST/SSE → FastAPI `:8000` → SQLite + LangGraph orchestrator.

## Conventions

- Package lives under `src/`; always use `--app-dir src` with uvicorn.
- Use `uv sync`, not raw pip.
- Local-first: SQLite only, single-user MVP.

## Gotchas

- Two processes required (API + Vite); frontend proxies to `:8000`.
- Default `USE_MOCK_LLM=true` in `.env.example`; set real keys and `USE_MOCK_LLM=false` for live LLM.
- Settings may write keys to project-root `.env` (gitignored).
- No `npm test` on frontend; use `npm run build` for FE checks.
- Port 8000 conflicts with other local services (e.g. claude-mem Chroma) — keep one listener.

## Agent workflows

- Large features: brainstorm → plan → small PR-sized steps.
- After changes: run `pytest` + `web` build before claiming done.
- Remember renames/decisions in local-memory (`StockResearch` was renamed from InvesBao).
