# AGENTS.md — `src/stockresearch` (Python backend)

Python backend package: FastAPI API + custom-orchestrated research agents + domain services. Runs under `uv` from the repo root; tests use `pythonpath = ["src"]`.

## Layout & boundaries

- `api/` — FastAPI app factory, routes, middleware, rate limiting, SSE responses, LLM dependency resolution. Keep HTTP concerns here; business logic belongs in `services/` and `agents/`.
- `agents/` — research/risk/chat agents on the custom orchestrator (graph, plan-execute, ReAct, SSE streaming). Emits the streaming events the web feed consumes.
- `services/` — domain/business logic shared by the API and agents.
- `data/` — market/news/data providers. External calls are isolated here; mock them in tests.
- `core/` — config (pydantic-settings) and the exception hierarchy.
- `db/` — SQLAlchemy models + session. Runtime `*.db` files are not committed.
- `worker.py` — background scheduler process (briefings, price alerts). `main.py` / `__main__.py` — CLI entry.

## Commands (run from repo root)

```bash
pytest tests/agents/                       # run one slice of the suite
uv run uvicorn stockresearch.api.app:app --reload --host 127.0.0.1 --port 8000 --app-dir src
uv run python -m stockresearch worker      # background schedulers
```

## Risk routing

- Cron/schedulers run in the separate `worker` process; the API only starts them when `RUN_SCHEDULERS_IN_API=true`. Don't assume timers start with the API.
- Don't commit runtime state (`src/scheduler.lock`, `*.db`); reset it rather than commit.
- Declared static checks (`mypy strict`, `ruff`) aren't all wired into CI yet — run them locally before pushing; the local pre-push hook runs full `pytest` + web build.
- Tests use in-memory SQLite + Mock LLM/market data; keep new tests hermetic (no network).
