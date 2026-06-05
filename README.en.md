# StockResearch

[中文](README.md) · [PRD](docs/PRD.md)

A **local, single-user Multi-Agent AI research terminal** for China A-share investors. Bloomberg-style web UI, LangGraph orchestration, **SQLite on your machine, BYOK in the browser** — no sign-up, no hosted SaaS, no paywall.

> **Disclaimer**: All AI output is for learning and research only. Not investment advice.

[![Tests](https://img.shields.io/badge/tests-138%20passed-brightgreen)](.)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

| Link | URL |
|------|-----|
| Source | [github.com/Miles128/StockResearch](https://github.com/Miles128/StockResearch) |
| PRD | [docs/PRD.md](docs/PRD.md) |

---

## Screenshots

### Chat (F1)

Natural-language entry with SSE streaming across four research dimensions, optional bull/bear debate, and judge synthesis. Header shows token usage and quote data source.

![Chat](docs/screenshots/chat.png)

### News (F2)

Three-layer rule-based feed grouped by holdings, sectors, and market; sector watchlist.

![News](docs/screenshots/news.png)

### Portfolio (F3)

Cost basis, lots, live P&amp;L, sector mix summary, one-click stock analysis.

![Portfolio](docs/screenshots/portfolio.png)

### Risk (F4)

Portfolio Sharpe, VaR, concentration, rule alerts, and LLM narrative.

![Risk](docs/screenshots/risk.png)

### Settings (F5)

BYOK LLM, optional Tushare token, debate toggle, report export, about.

![Settings](docs/screenshots/settings.png)

---

## Positioning

StockResearch is a **long-term open-source MVP**: a personal research workstation on your own PC, not a multi-tenant cloud product.

| Principle | Detail |
|-----------|--------|
| **Local-first** | `venv` + SQLite + `localhost`; no Docker/Redis/Postgres |
| **Single user** | Fixed local user `mvp`; no login |
| **Research before battle** | Four dimensions finish independently, then optional debate ([FinGenius](https://github.com/PbRQianJiang/FinGenius)) |
| **Tool isolation** | Each agent only calls domain tools ([TradingAgents](https://github.com/TauricResearch/TradingAgents)) |
| **Rules vs models** | News/risk thresholds are rule-based; LLM for reasoning |
| **BYOK** | API keys stay in the browser, never stored server-side |

---

## Features

| Module | Description |
|--------|-------------|
| Chat | Intent routing; ambiguous ticker picker |
| 4D research | Fundamental, technical, sentiment, chips (parallel ReAct) |
| Debate | Optional bull/bear rounds + judge |
| News | ≤3s SLA, zero LLM |
| Portfolio | P&amp;L, sectors, periodic refresh |
| Risk checkup | VaR, drawdown, concentration + AI summary |
| i18n | Chinese / English; two themes |

---

## Architecture

```
Browser (:5174)  ──REST/SSE──▶  FastAPI (:8000) + SQLite
                                    │
                              LangGraph Orchestrator
                                    │
                    quotes · news · sentiment · optional Tushare
```

---

## Quick start

**Requires** Python 3.12+, Node.js 18+

```bash
git clone https://github.com/Miles128/StockResearch.git
cd StockResearch

# Backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn stockresearch.api.app:app --reload --host 127.0.0.1 --port 8000 --app-dir src

# Frontend (new terminal)
cd web && npm install && npm run dev
```

Open **http://localhost:5174** and configure your LLM under **Settings** (BYOK). Works with [DeepSeek](https://platform.deepseek.com/), [DashScope compatible mode](https://help.aliyun.com/zh/model-studio/), and other OpenAI-compatible APIs.

```bash
pytest          # 138 tests
cd web && npm run build
```

---

## Environment

See [.env.example](.env.example).

| Variable | Purpose |
|----------|---------|
| `USE_MOCK_LLM` | Mock replies when `true` |
| `USE_MOCK_MARKET_DATA` | Simulated quotes when `true` |
| `LLM_HTTP_PROXY` | HTTP proxy for API calls, e.g. `http://127.0.0.1:7890` |

Browser LLM settings take precedence; `LLM_API_KEY` in `.env` can stay empty.

---

## Docs

- [PRD v3.0 (local single-user)](docs/PRD.md)
- [Initial development plan (baseline)](docs/DEVELOPMENT_PLAN.md)
- [中文 README](README.md)

---

## Contributing

Issues and PRs welcome. Read the PRD roadmap first to avoid duplicating planned work.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Disclaimer

All AI-generated content is for learning and technical discussion only. **Not investment advice.** You are solely responsible for investment decisions.
