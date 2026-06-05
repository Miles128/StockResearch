# StockResearch

两个晚上、拉着外部 Co 搓出来的 **A 股 Multi-Agent 投研玩具**——终端风界面，能聊天、能吵架（多空辩论）、能看盘。

> 所有 AI 输出仅供学习参考，**不构成投资建议**。

[![Tests](https://img.shields.io/badge/tests-113%20passed-brightgreen)](.)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

**在线演示（前端）**：[stockresearch-4kx.pages.dev](https://stockresearch-4kx.pages.dev)  
**仓库**：[github.com/Miles128/StockResearch](https://github.com/Miles128/StockResearch)

![AI 对话](docs/screenshots/chat.png)

---

## 这是什么

StockResearch 把「信息太多、看不完」这件事变轻一点：

- 你问个股或大盘，走 **四维投研**（基本面 / 技术面 / 情绪面 / 筹码面）
- 设置里打开 **多空辩论**，看多看空先吵完，裁判再总结——比一个人瞎琢磨热闹
- 快讯按持仓过滤，**3 秒内**出结果（规则引擎，不烧 LLM）
- 大模型 **BYOK**，API Key 只存本机浏览器

界面致敬 Bloomberg 终端；后端用 **LangGraph** 编排多 Agent，对话支持 **SSE 流式**输出全过程。

---

## 功能一览

| 模块 | 说明 |
|------|------|
| **智能对话** | 股票/市场 → 多维投研；设置可开关多空辩论；SSE 实时展示 Agent 过程 |
| **新闻快讯** | 三层噪音过滤 + 持仓相关度排序；3 秒 SLA |
| **持仓管理** | 录入成本/手数，实时盈亏，板块标签 |
| **风控体检** | 规则引擎（止损、集中度、黑天鹅）+ LLM 人话翻译 |
| **设置** | BYOK 大模型、多空辩论开关、中/英界面、主题切换 |

![投研](docs/screenshots/research.png)

---

## 架构

```
Web Terminal (React + Vite :5174)
        │  REST + SSE
        ▼
FastAPI (:8000)
        │
Orchestrator (LangGraph)
  ├── Chat Router     — 市场/个股意图识别 → 投研 / 直接回答 / 规划执行
  ├── Research        — 4× ReAct 子 Agent（工具隔离）+ 可选多空辩论 + 裁判
  ├── News            — 三层过滤，3s SLA，无 LLM
  └── Risk            — 规则 + LLM 翻译
        │
Data Layer (行情多源 / 新闻管道 / SQLite)
```

### 投研：四维独立 ReAct Agent

| 维度 | 工具示例 |
|------|----------|
| 基本面 | 财务指标、估值、同行对比 |
| 技术面 | K 线、MACD/RSI、实时行情 |
| 情绪面 | 雪球热度、个股新闻 |
| 筹码面 | 龙虎榜、资金流、股东户数、解禁 |

代码入口：`src/stockresearch/agents/research/agents/`、`stream.py`

### 对话路由逻辑

| 设置 | 股票/市场相关问题 | 其他问题 |
|------|-------------------|----------|
| 多空辩论 **开** | 四维分析 + 多空辩论 + 裁判 | 直接回答 / 规划执行 |
| 多空辩论 **关** | 四维分析（无辩论） | 直接回答 / 规划执行 |

---

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+（前端）

### 后端

```bash
cd StockResearch
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
python3.12 -m uvicorn stockresearch.api.app:app --reload --host 127.0.0.1 --port 8000 --app-dir src
```

API 文档：<http://127.0.0.1:8000/docs>

### 前端

```bash
cd web && npm install && npm run dev
```

**请访问 <http://localhost:5174>**（推荐 `localhost`，避免 IPv6 代理问题）。

首次打开需在设置中配置大模型（支持 OpenAI 兼容接口，如 DeepSeek、阿里云百炼 DashScope）。  
百炼 Base URL 填 `https://dashscope.aliyuncs.com/compatible-mode/v1` 即可，后端会自动补全 `/chat/completions`。

### Docker

```bash
docker compose up --build
```

### 测试

```bash
pytest
ruff check src tests
```

---

## 部署

| 目标 | 文档 |
|------|------|
| Cloudflare Pages（前端） | [docs/deploy-cloudflare.md](docs/deploy-cloudflare.md) |
| 自动部署（Pages + Fly） | [docs/deploy-auto.md](docs/deploy-auto.md) |

**切勿**在 Cloudflare / Fly 环境变量中配置 `LLM_API_KEY`——由用户浏览器 BYOK 传入。

---

## 环境变量

见 [.env.example](.env.example)。开发默认 `USE_MOCK_LLM=true` 可无外部 API 跑通演示。

| 变量 | 说明 |
|------|------|
| `LLM_BASE_URL` | OpenAI 兼容 Base URL（可为空，用户浏览器配置优先） |
| `LLM_API_KEY` | 服务端 Key（可选，生产建议留空） |
| `LLM_HTTP_PROXY` | 本机代理，如 `http://127.0.0.1:7890` |
| `USE_MOCK_LLM` | `true` 时用 Mock，不调用真实 API |

---

## 文档

- [产品 PRD（含路线图）](docs/PRD.md)
- [Multi-Agent 架构说明（旧版）](docs/投小宝_PRD_Multi_Agent架构.md)
- [项目开发规划](docs/投小宝_项目开发规划.md)

---

## 参考开源项目

灵感来自 [TradingAgents](https://github.com/TauricResearch/TradingAgents)、[TradingAgents-CN](https://github.com/hsliuping/TradingAgents-CN)、[FinGenius](https://github.com/PbRQianJiang/FinGenius)、[LangGraph](https://github.com/langchain-ai/langgraph) 等。

---

## 免责声明

本产品所有 AI 生成内容仅供学习与交流，不构成任何投资建议。市场有风险，决策靠自己。
