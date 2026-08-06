<div align="center">

# StockResearch · AI 投研终端

**开源 A 股 AI 研究 Agent — 本机运行 · 免费数据 · BYOK**

[![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python&logoColor=white)](pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-00C7B7?logo=fastapi&logoColor=white)](src/stockresearch/api/app.py)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white)](web/src/App.tsx)
[![Tauri](https://img.shields.io/badge/Tauri-2-24C8DB?logo=tauri&logoColor=white)](desktop)
[![Tests](https://img.shields.io/badge/tests-779%20passed-2ea44f)]()
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

**不连券商 · 不代交易 · 不编造数据 · 结论可事后验证**

</div>

---

## 两个北极星

> **① 预测准确率** — AI 分析尽可能准确预测市场。
> 不是"给买卖信号"，而是**可验证闭环**：每个预测被记录、到期评分、校准与归因学习——准确率可度量、可展示、可改进。
>
> **② 金融教育** — 让非专业人士更多了解金融市场。
> 不是平铺术语字典，而是**场景化教学**：知识在你查看估值分位、动量、风险敞口的当下零点击出现，术语解释绑到你自己持仓的数字上。

两者是**一切功能取舍的判据**（详见 [PRD §一 / §九·五](docs/PRD.md)）。

---

## 它是什么

本机联网运行的 **A 股 AI 研究助手**：自研多 Agent 编排投研 + React 三栏 UI + Tauri 桌面壳。帮助回答：**今天发生了什么 · 为什么与我有关 · 还需要验证什么 · 上次判断对不对**。

**产品对标 Google Finance**：免费的个人投资者行情与组合跟踪形态，用 AI 编排把专业投研能力平民化。

```text
┌─ 顶栏：指数 · 搜索 · 模式 · 告警铃 · 数据源 · 设置 ─────────────────────┐
├ lists ─────────┬─ center: [焦点][市场][风控][新闻] ┬─ Copilot ───────────┤
│ 持仓 · 自选    │ K线 · 多 Tab · 驾驶舱            │ 多线程 · SSE · 免责  │
└────────────────┴─────────────────────────────────┴───────────────────────┘
```

## 核心能力

| 能力 | 说明 |
|------|------|
| **四维投研** | 基本面 / 技术面 / 情绪 / 筹码，SSE 流式产出；每条结论附证据链；缺数显式 `partial`，禁止编造 |
| **深度分析三层** | Impact（为何涨跌·事件冲击）→ Pricing（现价定了什么·估值桥）→ Thesis（主张·监控·失效条件） |
| **验证引擎** | 复盘时间线 · 事后核对（PIT）· 事件研究 · 假设一键验证 · 研报卡「验证这条」入口 |
| **三档分析深度** | standard / comprehensive / deep（四维证据预算，非平行产品线） |
| **大盘四维投研** | 问"大盘怎么样"自动触发市场四维分析（宏观/行业/技术/情绪 + 多空辩论） |
| **每日简报** | 盘前 09:05 / 盘中 11:35 / 盘后 15:35 自动生成；盘后对照当日盘前观点；左侧栏历史回看 |
| **价格告警** | 5 分钟轮询 + 浏览器 Notification + **应用内通知中心**（已读管理，窗口关闭不丢） |
| **Action Center** | 零 LLM 规则信号（研究雷达 · 缺口补跑 · 风险追踪） |
| **双模式** | 个人（advisor 白话） / 专家（research 全量指标）——同一事实层，不同渲染 |
| **白话化** | reading_mode 两档 + 125 条金融词典 + 术语弹窗 + 数字翻译成影响 |
| **K 线画线** | 自动趋势线 / 水平支撑压力（前后端同一算法，跨端契约测试保证一致） |
| **数据备份** | 持仓/自选/交易/设置/研报索引一键导出 JSON（换机迁移） |
| **BYOK** | LLM / Tushare / 博查 Key 存浏览器或 `.env`，不上云 |

## 界面预览

| 今日关注 | 市场 | 风控 |
|:---:|:---:|:---:|
| ![今日关注](docs/screenshots/focus.png) | ![市场](docs/screenshots/market.png) | ![风控](docs/screenshots/risk.png) |

| 新闻 | Copilot | 设置 |
|:---:|:---:|:---:|
| ![新闻](docs/screenshots/news.png) | ![Copilot](docs/screenshots/copilot.png) | ![设置](docs/screenshots/settings.png) |

![贵州茅台投研分析](docs/screenshots/moutai-analysis.png)

---

## 快速开始

**环境**：Python 3.12+、[uv](https://docs.astral.sh/uv/)、Node.js 18+

```bash
git clone https://github.com/Miles128/StockResearch.git && cd StockResearch
uv sync && cp .env.example .env

# 终端 1 — API
uv run uvicorn stockresearch.api.app:app --reload --host 127.0.0.1 --port 8000 --app-dir src

# 终端 2 — 后台调度 worker（简报 / 价格告警 / 日线仓）
uv run python -m stockresearch worker

# 终端 3 — Web
cd web && npm install && npm run dev    # http://localhost:5174
```

首次引导：选模式 → Demo 持仓 → 配置 LLM（或 `.env` 里 `USE_MOCK_LLM=true` 先离线体验）。

**桌面壳**（Tauri 2，macOS / Windows）：

```bash
cd web && npm run build
cd ../desktop && npm install && npm run dev
```

详见 [desktop/README.md](desktop/README.md)。

### 命令行外带（JSON）

```bash
uv run stockresearch research timeline 600519        # 研究复盘时间线
uv run stockresearch research export <report_id>     # 导出报告
uv run stockresearch research hypothesis 600519      # 假设一键验证
```

便于 Jupyter / 管道消费；与 HTTP 研究验证 API 同源。

### 数据源

所有结论可追溯来源；失败时显式 `partial` / 降级，禁止 LLM 编造。多源价差 **>1%** 时顶栏黄色预警。

| 数据域 | 主源 | 备源（按序） |
|--------|------|--------------|
| 实时行情 | 新浪财经 | AkShare → efinance |
| K 线 | AkShare（前复权） | efinance → Tushare → 新浪 |
| 新闻快讯 | AkShare（东财） | 博查 AI 搜索（可选 Key） |
| 公告 / 研报 | 巨潮 / 东财 via AkShare | — |
| 财务 / 估值 | AkShare | Tushare Pro（可选增强） |
| 筹码 / 情绪 | AkShare | 雪球热度 |

**不做** Wind / iFinD / Choice 等万元级终端 API。

### 验证

```bash
uv run pytest && cd web && npm run build
```

Git 钩子（可选）：`pre-commit install --hook-type pre-commit --hook-type pre-push`（提交时 ruff/prettier，推送前全量 pytest + 前端 build）。

## 路线图

- **Phase 12 · 预测闭环**：预测日记 · 准确率仪表盘（含校准曲线）· 白话复盘 · 维度归因学习 · 假设自动验证 · Market Regime
- **Phase 13 · 金融教育**：场景化知识卡片 · Counterfactual 教学 · 新手投资日历 · 概念学习路径

已明确**不做**：邮件/短信推送、MCP server、策略回测器、实盘交易、移动 App。

## 文档

| 文档 | 说明 |
|------|------|
| [docs/PRD.md](docs/PRD.md) | 产品需求规格（V10.27，含北极星判据与路线图状态标注） |
| [AGENTS.md](AGENTS.md) | 开发约定：架构、调试、测试、分支策略 |
| [desktop/README.md](desktop/README.md) | 桌面壳说明 |

**免责声明**：AI 输出仅供学习与研究，不构成投资建议。

MIT — 见 [LICENSE](LICENSE)。
