# StockResearch

**[中文](#中文) · [English](#english)** · [PRD v8.7](docs/PRD.md)

[![Tests](https://img.shields.io/badge/backend-246%20passed-brightgreen)](.)
[![Frontend](https://img.shields.io/badge/frontend-22%20vitest%20passed-brightgreen)](.)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

| | |
|--|--|
| 源码 / Source | [github.com/Miles128/StockResearch](https://github.com/Miles128/StockResearch) |
| PRD | [docs/PRD.md](docs/PRD.md) |

---

## 本地 AI 原生投资研究 MVP

StockResearch 不是准备上线运营的股票服务，也不是传统终端再加一个聊天框。它是一个本地联网运行的产品原型，用来展示 AI 如何把持仓、行情、新闻、风险和多 Agent 研究组织成易理解、可追问的完整体验。

核心入口是「今天与我有关的变化」和自然语言任务，而不是密集菜单、指标矩阵与全市场扫描器。

```text
┌──────────────────────────────────────────────────────────┐
│ 上证  沪深300  深证  创业板       模式 / 数据 / 设置       │
├──────────────────────────────────────────────────────────┤
│ [持仓] [风控] [市场] [新闻·研报]              [AI 对话] │
├───────────────────────────────────────┬──────────────────┤
│               单一主画布               │ AI 对话          │
│                                       │ （横/竖排可切换） │
└───────────────────────────────────────┴──────────────────┘
```

AI 对话在所有工作区共用，但不会把所有内容混成一锅：

- 持仓、风险偏好和模式属于全局用户上下文；
- 连续问答与研究对象属于当前线程；
- 当前股票、新闻、组合或报告作为可见、可移除的临时页面上下文；
- 切换页面保留线程，但不会偷偷替换当前研究对象。

## 双模式 · Dual Mode

**个人**（默认）考虑你的现金流和风险承受能力，用大白话解释；**专家**专注四维深度分析，术语直出，不结合个人财务。顶栏一键切换，同一份数据，两种视角。

```
┌──────────────────────────────────────────────────────┐
│ StockResearch   [个人] [专家]      中/EN  数据  ⚙️   │
├──────────────────────────────────────────────────────┤
│      [持仓] [风控] [市场] [新闻·研报]  [AI 对话]     │
└──────────────────────────────────────────────────────┘
```

**两个核心差异**（其他差异都派生自这两点）：

| 核心差异 | 个人 | 专家 |
|---------|---------|---------|
| 现金流/风险承受能力 | 考虑（"浮亏 ¥2,300，相当于月收入 15%"） | 不考虑（纯指标 VaR 4.32%） |
| 语言表现 | 大白话，避免金融术语 | 术语直出，专业口径 |

| 其他维度 | 个人 | 专家 |
|---------|---------|---------|
| 信息密度 | 首屏 ≤ 5 条 | 完整数据 |
| 辩论 | 默认关 | 默认开 |
| 术语弹窗 | 默认开（PE / VaR 等悬浮解释） | 默认关 |

模式持久化，可随时切换；模式内单项可微调（Settings）。首次访问引导选模式 + 个人模式填风险分级/现金流 + 加载示例持仓。

---

## Screenshots · 界面预览

> 截图由 `scripts/capture_screenshots.mjs` 通过 Playwright 在 1440×900 视口下自动捕获，覆盖四个主视角 + AI 对话面板 + 设置面板。

### Portfolio · 持仓

成本与手数、实时盈亏、行业集中度、一键分析与 AI 快捷动作。

![Portfolio](docs/screenshots/portfolio.png)

### Risk · 风控

Sharpe、VaR、集中度、规则告警与 AI 解读；个人模式先人话，专家模式先指标。

![Risk](docs/screenshots/risk.png)

### Market · 市场

指数走势、市场宽度、强弱行业、AI 市场摘要。

![Market](docs/screenshots/market.png)

### News · 新闻·研报

三层规则过滤快讯，按持仓 / 板块 / 市场分组；可一键追问 AI。

![News](docs/screenshots/news.png)

### AI Chat · 全局 AI 对话

SSE 流式四维投研、多空辩论与裁判；支持横/竖排布局切换与可调宽度。

![Chat](docs/screenshots/chat.png)

### Settings · 设置

BYOK 大模型、博查 AI 搜索、可选 Tushare、辩论开关、报告导出、模式微调。

![Settings](docs/screenshots/settings.png)

---

<a id="中文"></a>

## 中文

面向 A 股个人投资者的 **双模式本机 AI 投资助手**。个人模式帮你看懂「今天发生了什么、为什么与我有关」，专家模式提供可展开的四维研究。项目只在本机运行，单用户、SQLite、BYOK，不注册、不上线、不连接交易。

> **免责声明**：所有 AI 输出仅供学习与研究参考，不构成任何投资建议。

### 产品定位

StockResearch 是**长期开源 MVP**：跑在你自己电脑上的投资助手，不是公网 SaaS。

| 原则 | 说明 |
|------|------|
| **双模式** | 个人（默认，人话+主动建议）/ 专家（术语+深度），顶栏一键切换 |
| **本机优先** | `venv` + SQLite + `localhost`，无 Docker/Redis/Postgres |
| **单用户** | 固定本地用户 `mvp`，无需登录 |
| **同一份数据** | 双模式共享后端推理与数据，只有呈现层和写作风格按模式切换 |
| **Research 先于 Battle** | 四维研究完成后再可选多空辩论 |
| **工具隔离** | 各维度 Agent 仅调用本域工具 |
| **规则与模型分工** | 快讯/风控走规则；LLM 负责推理与生成 |
| **BYOK** | Key 不进入数据库；可保存在浏览器，或由用户明确写入本机 `.env` |
| **真实联网** | 默认连接真实行情和新闻；Mock 仅用于无 Key 演示和显式降级 |
| **数据源透明** | AI 结论可查看来源、时间、缓存、Mock、降级与冲突状态 |
| **健康自检** | 顶部 `BackendHealthBanner` 监控后端可用性，宕机时红色提示 |

### 功能一览

| 模块 | 说明 |
|------|------|
| **双模式切换** | 顶栏个人/专家一键切换，持久化，模式内可微调 |
| **全局 AI 对话** | 所有工作区共享外壳；横/竖排布局可切换，宽度可调；线程延续，页面上下文显式附加 |
| **首次引导** | 选模式 + 示例持仓 + LLM 配置，3 步完成 |
| 智能对话 | 个股/市场意图路由；歧义股票卡片确认 |
| 四维投研 | 基本面、技术面、情绪面、筹码面 ReAct 并行 |
| A 股因子检查 | 研究报告可展开查看涨跌停/ST、龙虎榜、资金、解禁、财务、技术结构等验证状态和来源明细 |
| 多空辩论 | 设置中可开关（个人默认关，专家默认开） |
| 新闻快讯 | ≤3s SLA，零 LLM；博查 AI 联网搜索兜底 |
| 巨潮公告 | 上市公司公告 provider |
| 研报中心 | 东方财富研报 provider |
| 持仓管理 | 成本、盈亏、板块、定时刷新；收盘后停止刷新 |
| 风控体检 | VaR、回撤、集中度 + AI 解读（个人先人话，专家先指标） |
| 数据源详情 | 顶栏点击数据状态，查看真实源、缓存、Mock、降级和增强数据配置 |
| 后端健康监控 | 后端不可用时顶部红色横幅提示，避免误判前端 bug |
| 简报定时任务 | APScheduler 盘前 09:00 / 收盘 15:30，仅 A 股交易日执行 |
| 国际化 | 中/英界面；橙黑 / 酒红主题 |

### 架构

```
┌─────────────────────────────────────────────────────┐
│  模式层  个人 ←→ 专家  顶栏切换 · 持久化             │
├─────────────────────────────────────────────────────┤
│  呈现层（前端，按模式差异化）                          │
├─────────────────────────────────────────────────────┤
│  推理层（后端，模式无关）LangGraph + 四维 ReAct + 辩论 │
├─────────────────────────────────────────────────────┤
│  数据层（后端，模式无关）行情 · 新闻 · 财报 · 持仓     │
└─────────────────────────────────────────────────────┘

浏览器 (:5174)  ──REST/SSE──▶  FastAPI (:8000) + SQLite
```

### 快速开始

**环境**：Python 3.12+、[uv](https://docs.astral.sh/uv/)、Node.js 18+

```bash
git clone https://github.com/Miles128/StockResearch.git
cd StockResearch

# 后端（uv 管理虚拟环境与依赖，见 uv.lock）
uv sync
cp .env.example .env   # 编辑 .env 填写 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
uv run uvicorn stockresearch.api.app:app --reload --host 127.0.0.1 --port 8000 --app-dir src

# 前端（新终端）
cd web && npm install && npm run dev
```

打开 **http://localhost:5174**。首次进入触发引导：选模式（个人/专家）→ 示例持仓已加载 → 配置 LLM（或 Mock 模式先体验）。也可随时按 **F5** 打开设置页。保存后自动写入项目根 `.env`（已 gitignore）。支持 [DeepSeek](https://platform.deepseek.com/)、[DashScope 兼容模式](https://help.aliyun.com/zh/model-studio/) 等 OpenAI 兼容接口。

```bash
pytest          # 246 tests
cd web && npm run lint && npm run build && npm test   # 22 vitest tests

# 显式验证真实新浪 / 东方财富等外网 Provider
RUN_LIVE_TESTS=1 pytest -m live

# 重新生成界面截图（需先启动前后端）
SCREENSHOT_BASE_URL=http://127.0.0.1:5174 node scripts/capture_screenshots.mjs
```

### 环境变量

见 [.env.example](.env.example)。

| 变量 | 说明 |
|------|------|
| `LLM_API_KEY` | 本机大模型 Key（勿提交） |
| `LLM_BASE_URL` | OpenAI 兼容 Base URL，如 `https://api.deepseek.com/v1` |
| `LLM_MODEL` | 模型名，如 `deepseek-chat` |
| `USE_MOCK_LLM` | `true` 时 Mock 回复，便于无 Key 演示 |
| `LLM_HTTP_PROXY` | 本机访问 API 的代理，如 `http://127.0.0.1:7890` |
| `BOCHA_API_KEY` | 博查 AI 联网搜索 Key（新闻兜底；留空则跳过联网搜索） |

在设置页保存后，后端从 `.env` 读取；无需每次在浏览器重复填 Key。

### 文档与贡献

- [PRD v8.7（单画布 + AI 对话 + 分层数据源 + 健康监控）](docs/PRD.md)
- 历史 `docs/DEVELOPMENT_PLAN.md` 已废弃，请以 PRD 为准
- 欢迎 Issue 与 PR；开发前请阅读 PRD 路线图

### 许可证与免责

MIT — 见 [LICENSE](LICENSE)。本产品 AI 内容仅供学习与研究，**不构成投资建议**。

---

<a id="english"></a>

## English

A **dual-mode local AI investment assistant** for China A-share investors. **Advisor mode** considers your cash flow and risk tolerance, explaining in plain language; **Research mode** focuses on four-dimensional deep analysis with direct terminology, not tied to personal finances. LangGraph orchestration, **SQLite on your machine, BYOK in the browser** — no sign-up, no hosted SaaS, no paywall.

> **Disclaimer**: All AI output is for learning and research only. Not investment advice.

### Positioning

StockResearch is a **long-term open-source MVP**: a personal investment assistant on your PC, not a multi-tenant cloud product.

| Principle | Detail |
|-----------|--------|
| **Dual mode** | Advisor (default, plain language + proactive) / Research (terms + depth), top-bar toggle |
| **Local-first** | `venv` + SQLite + `localhost`; no Docker/Redis/Postgres |
| **Single user** | Fixed local user `mvp`; no login |
| **Same data** | Both modes share backend reasoning & data; only presentation and writing style switch |
| **Research before battle** | Four dimensions finish independently, then optional debate |
| **Tool isolation** | Each agent only calls domain tools |
| **Rules vs models** | News/risk thresholds are rule-based; LLM for reasoning |
| **BYOK** | API keys stay in the browser, never stored server-side |
| **Backend health** | Top `BackendHealthBanner` warns when API is down |

### Features

| Module | Description |
|--------|-------------|
| **Dual-mode toggle** | Top-bar Advisor/Research switch, persisted, fine-tunable per mode |
| **Global AI chat** | Shared shell across workspaces; horizontal/vertical layout toggle, resizable; thread continues, page context explicit |
| **Onboarding** | Pick mode + demo holdings + LLM config in 3 steps |
| Chat | Intent routing; ambiguous ticker picker |
| 4D research | Fundamental, technical, sentiment, chips (parallel ReAct) |
| Debate | Optional bull/bear rounds + judge (off in Advisor, on in Research) |
| News | ≤3s SLA, zero LLM; Bocha AI search fallback |
| CNInfo announcements | Listed-company announcement provider |
| Research reports | East Money research report provider |
| Portfolio | P&amp;L, sectors, periodic refresh; stops refreshing after market close |
| Risk checkup | VaR, drawdown, concentration + AI summary (Advisor: plain first; Research: metrics first) |
| Data source details | Click top status badge to view real source, cache, Mock, degradation, enhanced config |
| Backend health | Red banner when backend unreachable |
| Scheduled briefing | APScheduler pre-market 09:00 / post-close 15:30, A-share trading days only |
| i18n | Chinese / English UI; two themes |

### Architecture

```
┌─────────────────────────────────────────────────────┐
│  Mode layer  Advisor ←→ Research  top-bar · persist  │
├─────────────────────────────────────────────────────┤
│  Presentation (frontend, mode-differentiated)        │
├─────────────────────────────────────────────────────┤
│  Reasoning (backend, mode-agnostic) LangGraph + 4D  │
├─────────────────────────────────────────────────────┤
│  Data (backend, mode-agnostic) quotes·news·reports  │
└─────────────────────────────────────────────────────┘

Browser (:5174)  ──REST/SSE──▶  FastAPI (:8000) + SQLite
```

### Quick start

**Requires** Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 18+

```bash
git clone https://github.com/Miles128/StockResearch.git
cd StockResearch

# Backend (uv manages the venv; see uv.lock)
uv sync
cp .env.example .env   # set LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
uv run uvicorn stockresearch.api.app:app --reload --host 127.0.0.1 --port 8000 --app-dir src

# Frontend (new terminal)
cd web && npm install && npm run dev
```

Open **http://localhost:5174**. First visit triggers onboarding: pick mode (Advisor/Research) → demo holdings loaded → configure LLM (or Mock mode). Press **F5** anytime for Settings. Saving writes to the project root `.env` (gitignored) automatically. Works with [DeepSeek](https://platform.deepseek.com/), [DashScope compatible mode](https://help.aliyun.com/zh/model-studio/), and other OpenAI-compatible APIs.

```bash
pytest          # 246 tests
cd web && npm run lint && npm run build && npm test   # 22 vitest tests

# Regenerate screenshots (start backend + frontend first)
SCREENSHOT_BASE_URL=http://127.0.0.1:5174 node scripts/capture_screenshots.mjs
```

### Environment

See [.env.example](.env.example).

| Variable | Purpose |
|----------|---------|
| `LLM_API_KEY` | Local LLM API key (never commit) |
| `LLM_BASE_URL` | OpenAI-compatible base URL |
| `LLM_MODEL` | Model id, e.g. `deepseek-chat` |
| `USE_MOCK_LLM` | Mock replies when `true` |
| `LLM_HTTP_PROXY` | HTTP proxy for API calls, e.g. `http://127.0.0.1:7890` |
| `BOCHA_API_KEY` | Bocha AI web search key (news fallback; skipped if empty) |

Saving in Settings writes `.env`; the backend reads it on the next request.

### Docs & contributing

- [PRD v8.7 (single canvas + AI Chat + layered data sources + health monitoring)](docs/PRD.md)
- Legacy `docs/DEVELOPMENT_PLAN.md` is deprecated; refer to PRD
- Issues and PRs welcome; read the PRD roadmap before large features

### License & disclaimer

MIT — see [LICENSE](LICENSE). AI output is for learning and research only. **Not investment advice.**
