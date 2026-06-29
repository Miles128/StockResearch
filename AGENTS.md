# AGENTS.md — StockResearch

AI stock research assistant. LangGraph backend + React tri-shell UI (lists · focus · copilot).

## Quick start

```bash
cd "/Users/sihai/Documents/My Projects/StockResearch"
uv sync && cp .env.example .env
cd web && npm install
```

```bash
uv run uvicorn stockresearch.api.app:app --reload --host 127.0.0.1 --port 8000 --app-dir src
cd web && npm run dev   # :5174
```

## Verification

```bash
pytest && cd web && npm run build
```

## Documentation

- **PRD:** `docs/PRD.md` (only product spec)
- **Meta:** `docs/meta.yaml` (prd-first fields)
- **Screenshots:** `docs/screenshots/` (README assets only)

**Rules:** Do not add PRD copies under `documents/`, `.prd/`, or repo root. Do not add extra markdown specs under `docs/` — update `docs/PRD.md` §十一 instead.

## Architecture

Center tabs: **focus | risk | news** (no fourth market tab). Copilot is global right rail.

Cron (briefings, price alerts) runs inside uvicorn lifespan.

## Active branch note

Latest UI is on `codex/ai-native-mvp-canvas` (may be ahead of `main`). Prefer that branch for tri-shell work.
