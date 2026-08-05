# AGENTS.md — StockResearch

AI stock research assistant. Custom multi-agent orchestration backend + React tri-shell UI (lists · focus · copilot).

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

## Debugging

**日志输出位置** — 后端不写日志文件。API（`src/stockresearch/api/app.py`）与 worker（`src/stockresearch/worker.py`）都在启动时执行 `logging.basicConfig(level=INFO, format="%(asctime)s %(levelname)-5s %(name)s | %(message)s")`，输出到各自进程的 stdout/stderr，即启动它们的终端（uvicorn 自身日志同样在终端）；`%(name)s` 为模块名（如 `stockresearch.agents.orchestrator.stream`）。需要落盘时自行重定向（如 `2>&1 | tee api.log`），不要改动上面的启动命令。

运行时数据都在 SQLite：`.env` 的 `DATABASE_URL=sqlite:///./main.db` 相对启动进程的工作目录解析，当前实际文件在 `src/main.db`（`-wal`/`-shm` 同目录）；调度锁文件 `src/scheduler.lock`（内容为持锁进程 PID）。

**会话归因** — 一次聊天运行的所有后端日志都带 `[sid=<session_id>]` 前缀（见 `agents/orchestrator/react_agent.py::_log_ctx`、`agents/orchestrator/stream.py`、`agents/orchestrator/chat_execute.py`）。`session_id` 由前端线程持有（localStorage key `stockresearch.copilotThreads`，见 `web/src/copilotThreads.ts`），首次对话由后端生成并随响应返回。拿到 `sid` 后可反查 DB `conversations` 表（`session_id` 唯一索引；`messages`/`checkpoint` JSON、`updated_at`），把一次运行时失败归因到具体会话。

**诊断入口**

- `GET /health` — 进程存活检查
- `GET /api/v1` 与 `/docs` — 端点清单与 Swagger UI
- `GET /api/v1/chat/checkpoint/{session_id}` — 按会话查流式断点（`services/stream_checkpoint.py`）
- `POST /api/v1/settings/llm/test` — LLM 连通性自检
- `uv run python -m stockresearch research timeline|hypothesis|compare|export <symbol|report_id>` — 不依赖 Web/API 的复盘/导出 CLI

**常用复现步骤**

1. Copilot 分析失败：UI 发消息 → 在 API 终端 `grep -F "[sid="` 过滤本次运行 → 定位 ERROR/WARNING 与堆栈 → 用 `sid` 查 `conversations` 表核对消息与断点。
2. 简报/价格告警没跑：worker 终端出现 `Another process holds the scheduler lock`（或 API 的 `Schedulers disabled in API`）→ `RUN_SCHEDULERS_IN_API` 与 worker 只能二选一 → 看 `src/scheduler.lock` 的 PID 确认持锁进程。
3. LLM 报错：日志 `[sid=...] LLM config error ...`，API 返回 `llm_not_configured`（503）→ 用 `POST /api/v1/settings/llm/test` 验证连通性与 Key。

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
