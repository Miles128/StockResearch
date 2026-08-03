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

桌面壳（Tauri 2，macOS/Windows；需先 `cd web && npm run build`）：

```bash
cd desktop && npm install && npm run dev
```

详见 `desktop/README.md`。

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

Git hooks are declared in `.pre-commit-config.yaml` (ruff/prettier on commit; full `pytest` + `npm run build` on pre-push) but are **not installed by default** — activate them once with `pre-commit install --hook-type pre-commit --hook-type pre-push` (requires the `pre-commit` tool). Otherwise run the full suite + build above manually before every push; remote CI is the only otherwise-enforced gate.

## Documentation

- **PRD:** `docs/PRD.md`
- **UI screenshots:** `docs/screenshots/` (regenerate with `scripts/capture_screenshots.mjs`)
- **Local only:** `docs/meta.yaml` (prd-first)

**Rules:** Do not add PRD copies under `documents/`, `.prd/`, or repo root. Do not track other files under `docs/` except `PRD.md` and `screenshots/` — update `docs/PRD.md` §十 instead.

## Architecture

Center tabs: **focus | market | risk | news**. Copilot is global right rail.

Cron (briefings, price alerts) runs in a separate `stockresearch worker` process; API lifespan only starts schedulers when `RUN_SCHEDULERS_IN_API=true`.

## Branching

`main` is the integration branch; day-to-day work happens on `feat/**` and `fix/**` branches, which (together with `main`) are the branches CI runs on. Merge back to `main` via PR. Before reusing any long-lived branch, check its freshness against `main` (e.g. `git rev-list --left-right --count main...<branch>`) — do not base new work on a stale branch.
