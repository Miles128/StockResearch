# StockResearch

**[中文](#中文) · [English](#english)** · [PRD v10.1](docs/PRD.md)

[![Python](https://img.shields.io/badge/python-3.12+-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

| | |
|--|--|
| 源码 / Source | [github.com/Miles128/StockResearch](https://github.com/Miles128/StockResearch) |
| PRD | [docs/PRD.md](docs/PRD.md) |

---

## 开源 A 股市场研究 Agent

本机运行的 A 股 AI 研究助手：LangGraph 多 Agent 投研 + React 三栏 UI。**不连券商、不代交易**，帮助理解「今天发生了什么、与我何关、还需验证什么」。

```text
┌─ 顶栏：指数 · 搜索 · 模式 · 告警 · 数据源 · 设置 ─────────────────────┐
├ lists ─────────┬─ center: [焦点][市场][风控][新闻] ┬─ Copilot ───────────┤
│ 持仓 · 自选    │ K线 · 多 Tab · ActionCenter      │ 多线程 · SSE · 免责  │
└────────────────┴─────────────────────────────────┴───────────────────────┘
```

- **个人 / 专家**双模式：同一事实层 JSON，不同渲染密度与合规过滤
- **Copilot** 驱动焦点 Tab（分析某股 → 新开 Tab；对比 → 交叉分析）
- **BYOK**：LLM / Tushare / 博查 Key 存浏览器或 `.env`，不上云

> **免责声明**：AI 输出仅供学习与研究，不构成投资建议。

---

## 数据源

所有结论可追溯来源；失败时显式 `partial` / 降级，禁止 LLM 编造。多源价差 **>1%** 时顶栏黄色预警。

| 数据域 | 主源 | 备源（按序） | 说明 |
|--------|------|--------------|------|
| **实时行情** | [新浪财经](https://finance.sina.com.cn) `hq.sinajs.cn` | AkShare → [efinance](https://github.com/Micro-sheep/efinance) | 三源兜底；Sina 与 AkShare 价差 >1% 告警 |
| **K 线** | AkShare（前复权） | 新浪 → efinance | 指数用 `index_zh_a_hist` |
| **指数概览** | 新浪指数 | AkShare | 北向资金：AkShare 东方财富接口 |
| **新闻快讯** | AkShare（东方财富） | [博查 AI 搜索](https://open.bochaai.com) | 博查需 `BOCHA_API_KEY`；≤3s SLA，零 LLM |
| **公告** | 巨潮资讯 via AkShare | — | `stock_zh_a_disclosure_report_cninfo` |
| **机构研报** | 东方财富 via AkShare | — | `stock_research_report_em` |
| **财务/估值** | AkShare | **Tushare Pro**（可选） | 有 Tushare Token 时优先；冲突 UI 并列预警 |
| **筹码/情绪** | AkShare | 雪球热度 | 龙虎榜、资金流、北向、两融、股东户数、解禁等 |

**不做** iFinD / Wind / Choice 等万元级终端 API。

---

## 界面预览

| 今日关注 | 市场 | 风控 |
|:---:|:---:|:---:|
| ![今日关注](docs/screenshots/focus.png) | ![市场](docs/screenshots/market.png) | ![风控](docs/screenshots/risk.png) |

| 新闻 | Copilot | 设置 |
|:---:|:---:|:---:|
| ![新闻](docs/screenshots/news.png) | ![Copilot](docs/screenshots/copilot.png) | ![设置](docs/screenshots/settings.png) |

![贵州茅台投研分析](docs/screenshots/moutai-analysis.png)

---

<a id="中文"></a>

## 中文

### 快速开始

**环境**：Python 3.12+、[uv](https://docs.astral.sh/uv/)、Node.js 18+

```bash
git clone https://github.com/Miles128/StockResearch.git && cd StockResearch
uv sync && cp .env.example .env

# 终端 1 — API
uv run uvicorn stockresearch.api.app:app --reload --host 127.0.0.1 --port 8000 --app-dir src

# 终端 2 — 后台调度 worker（简报/价格告警）
uv run python -m stockresearch worker

# 终端 3 — Web
cd web && npm install && npm run dev
```

打开 **http://localhost:5174**。首次引导：选模式 → Demo 持仓 → 配置 LLM（或 `USE_MOCK_LLM=true` 先体验）。

桌面壳（Tauri 2，macOS / Windows；需本机 `uv` + 已构建前端）：

```bash
cd web && npm run build
cd ../desktop && npm install && npm run dev
```

详见 [desktop/README.md](desktop/README.md)。

### 环境变量

见 [.env.example](.env.example)。

| 变量 | 说明 |
|------|------|
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | OpenAI 兼容大模型（DeepSeek、DashScope 等） |
| `USE_MOCK_LLM` | `true` 无 Key 演示 |
| `BOCHA_API_KEY` | 博查联网搜索（新闻兜底，可留空） |

Tushare Token 在设置页填写（浏览器 BYOK），非 `.env` 必填项。

### 验证

```bash
uv run pytest && cd web && npm run build
```

### 文档

- 产品规格：[docs/PRD.md](docs/PRD.md)
- Agent 开发：[AGENTS.md](AGENTS.md)

MIT — 见 [LICENSE](LICENSE)。

---

<a id="english"></a>

## English

Open-source **A-share market research agent** running locally. LangGraph multi-agent research + React tri-shell UI (lists · focus · copilot). No broker connection, no trading.

**Dual mode**: Advisor (plain language) / Research (full metrics) — same fact layer, different rendering.

### Quick start

```bash
git clone https://github.com/Miles128/StockResearch.git && cd StockResearch
uv sync && cp .env.example .env

# Terminal 1 — API
uv run uvicorn stockresearch.api.app:app --reload --host 127.0.0.1 --port 8000 --app-dir src

# Terminal 2 — Background worker (briefings & price alerts)
uv run python -m stockresearch worker

# Terminal 3 — Web
cd web && npm install && npm run dev   # http://localhost:5174
```

Desktop shell (Tauri 2, macOS/Windows): build `web` first, then `cd desktop && npm install && npm run dev`. See [desktop/README.md](desktop/README.md).

### Data sources

See the table above. Layered fallbacks: **Sina → AkShare → efinance** for quotes; **AkShare → Sina → efinance** for K-lines. News via AkShare with optional Bocha web search. Optional Tushare Pro for financials. No Wind/iFinD/Choice.

### Verify

```bash
uv run pytest && cd web && npm run build
```

Full spec: [docs/PRD.md](docs/PRD.md) · MIT [LICENSE](LICENSE).
