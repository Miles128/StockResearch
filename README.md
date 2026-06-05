# StockResearch

**[中文](#中文) · [English](#english)** · [PRD](docs/PRD.md)

[![Tests](https://img.shields.io/badge/tests-141%20passed-brightgreen)](.)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

| | |
|--|--|
| 源码 / Source | [github.com/Miles128/StockResearch](https://github.com/Miles128/StockResearch) |
| PRD | [docs/PRD.md](docs/PRD.md) |

---

## Screenshots · 界面预览

### Chat · 对话 (F1)

Natural-language entry with SSE streaming; four research dimensions, optional debate, judge synthesis. Token usage and quote source in the header.

自然语言入口，SSE 流式展示四维投研、多空辩论与裁判；顶栏显示 Token 用量与行情源。

![Chat](docs/screenshots/chat.png)

### News · 新闻 (F2)

Three-layer rule-based feed by holdings, sectors, and market.

三层规则过滤快讯，按持仓 / 板块 / 市场分组。

![News](docs/screenshots/news.png)

### Portfolio · 持仓 (F3)

Cost, lots, live P&amp;L, sector mix, one-click analysis.

成本与手数、实时盈亏、行业集中度、一键分析。

![Portfolio](docs/screenshots/portfolio.png)

### Risk · 风控 (F4)

Sharpe, VaR, concentration, rule alerts, LLM narrative.

Sharpe、VaR、集中度、规则告警与 AI 解读。

![Risk](docs/screenshots/risk.png)

### Settings · 设置 (F5)

BYOK LLM, optional Tushare token, debate toggle, report export.

BYOK 大模型、可选 Tushare、辩论开关、报告导出。

![Settings](docs/screenshots/settings.png)

---

<a id="中文"></a>

## 中文

面向 A 股个人投资者的 **本机 Multi-Agent AI 投研终端**。Bloomberg 风格 Web 界面，LangGraph 编排专用 Agent，**单用户、SQLite、浏览器 BYOK**——不注册、不上线、不收费。

> **免责声明**：所有 AI 输出仅供学习与研究参考，不构成任何投资建议。

### 产品定位

StockResearch 是**长期开源 MVP**：跑在你自己电脑上的投研工作台，不是公网 SaaS。

| 原则 | 说明 |
|------|------|
| **本机优先** | `venv` + SQLite + `localhost`，无 Docker/Redis/Postgres |
| **单用户** | 固定本地用户 `mvp`，无需登录 |
| **Research 先于 Battle** | 四维研究完成后再可选多空辩论（[FinGenius](https://github.com/HuaYaoAI/FinGenius)） |
| **工具隔离** | 各维度 Agent 仅调用本域工具（[TradingAgents](https://github.com/TauricResearch/TradingAgents)） |
| **规则与模型分工** | 快讯/风控走规则；LLM 负责推理与生成 |
| **BYOK** | API Key 仅存浏览器，不经服务端数据库 |

### 功能一览

| 模块 | 说明 |
|------|------|
| 智能对话 | 个股/市场意图路由；歧义股票卡片确认 |
| 四维投研 | 基本面、技术面、情绪面、筹码面 ReAct 并行 |
| 多空辩论 | 设置中可开关 |
| 新闻快讯 | ≤3s SLA，零 LLM |
| 持仓管理 | 成本、盈亏、板块、定时刷新 |
| 风控体检 | VaR、回撤、集中度 + AI 解读 |
| 国际化 | 中/英界面；橙黑 / 酒红主题 |

### 架构

```
浏览器 (:5174)  ──REST/SSE──▶  FastAPI (:8000) + SQLite
                                    │
                              LangGraph Orchestrator
                                    │
                    行情 · 新闻 · 情绪 · 可选 Tushare
```

### 快速开始

**环境**：Python 3.12+、Node.js 18+

```bash
git clone https://github.com/Miles128/StockResearch.git
cd StockResearch

# 后端
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn stockresearch.api.app:app --reload --host 127.0.0.1 --port 8000 --app-dir src

# 前端（新终端）
cd web && npm install && npm run dev
```

打开 **http://localhost:5174**，在「设置」中配置大模型（BYOK）。支持 [DeepSeek](https://platform.deepseek.com/)、[DashScope 兼容模式](https://help.aliyun.com/zh/model-studio/) 等 OpenAI 兼容接口。

```bash
pytest          # 141 tests
cd web && npm run build
```

### 环境变量

见 [.env.example](.env.example)。

| 变量 | 说明 |
|------|------|
| `USE_MOCK_LLM` | `true` 时 Mock 回复，便于无 Key 演示 |
| `USE_MOCK_MARKET_DATA` | `true` 时模拟行情 |
| `LLM_HTTP_PROXY` | 本机访问 API 的代理，如 `http://127.0.0.1:7890` |

LLM Key 优先使用浏览器设置，`.env` 中的 `LLM_API_KEY` 可留空。

### 文档与贡献

- [PRD v3.0（单用户本机）](docs/PRD.md)
- [初版开发规划](docs/DEVELOPMENT_PLAN.md)
- 欢迎 Issue 与 PR；开发前请阅读 PRD 路线图

### 许可证与免责

MIT — 见 [LICENSE](LICENSE)。本产品 AI 内容仅供学习与研究，**不构成投资建议**。

---

<a id="english"></a>

## English

A **local, single-user Multi-Agent AI research terminal** for China A-share investors. Bloomberg-style web UI, LangGraph orchestration, **SQLite on your machine, BYOK in the browser** — no sign-up, no hosted SaaS, no paywall.

> **Disclaimer**: All AI output is for learning and research only. Not investment advice.

### Positioning

StockResearch is a **long-term open-source MVP**: a personal research workstation on your PC, not a multi-tenant cloud product.

| Principle | Detail |
|-----------|--------|
| **Local-first** | `venv` + SQLite + `localhost`; no Docker/Redis/Postgres |
| **Single user** | Fixed local user `mvp`; no login |
| **Research before battle** | Four dimensions finish independently, then optional debate ([FinGenius](https://github.com/HuaYaoAI/FinGenius)) |
| **Tool isolation** | Each agent only calls domain tools ([TradingAgents](https://github.com/TauricResearch/TradingAgents)) |
| **Rules vs models** | News/risk thresholds are rule-based; LLM for reasoning |
| **BYOK** | API keys stay in the browser, never stored server-side |

### Features

| Module | Description |
|--------|-------------|
| Chat | Intent routing; ambiguous ticker picker |
| 4D research | Fundamental, technical, sentiment, chips (parallel ReAct) |
| Debate | Optional bull/bear rounds + judge |
| News | ≤3s SLA, zero LLM |
| Portfolio | P&amp;L, sectors, periodic refresh |
| Risk checkup | VaR, drawdown, concentration + AI summary |
| i18n | Chinese / English UI; two themes |

### Architecture

```
Browser (:5174)  ──REST/SSE──▶  FastAPI (:8000) + SQLite
                                    │
                              LangGraph Orchestrator
                                    │
                    quotes · news · sentiment · optional Tushare
```

### Quick start

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
pytest          # 141 tests
cd web && npm run build
```

### Environment

See [.env.example](.env.example).

| Variable | Purpose |
|----------|---------|
| `USE_MOCK_LLM` | Mock replies when `true` |
| `USE_MOCK_MARKET_DATA` | Simulated quotes when `true` |
| `LLM_HTTP_PROXY` | HTTP proxy for API calls, e.g. `http://127.0.0.1:7890` |

Browser LLM settings take precedence; `LLM_API_KEY` in `.env` can stay empty.

### Docs & contributing

- [PRD v3.0 (local single-user)](docs/PRD.md)
- [Initial development plan (baseline)](docs/DEVELOPMENT_PLAN.md)
- Issues and PRs welcome; read the PRD roadmap before large features

### License & disclaimer

MIT — see [LICENSE](LICENSE). AI output is for learning and research only. **Not investment advice.**
