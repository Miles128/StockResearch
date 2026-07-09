# AGENTS.md — StockResearch

AI stock research assistant. LangGraph backend + React tri-shell UI (lists · focus · copilot).

## Quick start

```bash
cd "/Users/sihai/Documents/My Projects/StockResearch"
uv sync && cp .env.example .env
cd web && npm install
```

```bash
# 终端 1 — API
uv run uvicorn stockresearch.api.app:app --reload --host 127.0.0.1 --port 8000 --app-dir src

# 终端 2 — 后台调度 worker（简报/价格告警）
uv run python -m stockresearch worker

# 终端 3 — Web
cd web && npm run dev   # :5174
```

## Testing

**During development** — run only what you touched:

```bash
pytest tests/services/test_compliance_language.py   # one file
pytest tests/agents/                               # one directory
```

**Before claiming done or pushing** — full suite + frontend build:

```bash
pytest && cd web && npm run build
```

`pre-push` hook runs full `pytest` and `npm run build` automatically.

## Documentation

- **PRD:** `docs/PRD.md` — **only file under `docs/` pushed to GitHub**
- **Local only:** `docs/meta.yaml` (prd-first), `docs/screenshots/` (capture script output)

**Rules:** Do not add PRD copies under `documents/`, `.prd/`, or repo root. Do not track other files under `docs/` — update `docs/PRD.md` §十 instead.

## Architecture

Center tabs: **focus | market | risk | news**. Copilot is global right rail.

Cron (briefings, price alerts) runs in a separate `stockresearch worker` process; API lifespan only starts schedulers when `RUN_SCHEDULERS_IN_API=true`.

## Active branch note

Latest UI is on `codex/ai-native-mvp-canvas` (may be ahead of `main`). Prefer that branch for tri-shell work.
