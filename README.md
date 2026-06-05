# StockResearch

面向 A 股个人投资者的 **Multi-Agent AI 投研终端**。采用 Bloomberg 风格 Web 界面，以 LangGraph 编排多个专用 Agent，提供流式对话、四维投研、可选多空辩论、快讯过滤与持仓风控能力。

> **免责声明**：本产品所有 AI 输出仅供学习与研究参考，不构成任何投资建议。

[![Tests](https://img.shields.io/badge/tests-113%20passed-brightgreen)](.)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

| 链接 | 地址 |
|------|------|
| 在线演示（前端） | [stockresearch-4kx.pages.dev](https://stockresearch-4kx.pages.dev) |
| 源码仓库 | [github.com/Miles128/StockResearch](https://github.com/Miles128/StockResearch) |
| 产品 PRD | [docs/PRD.md](docs/PRD.md) |

![AI 对话](docs/screenshots/chat.png)

---

## 产品定位

StockResearch 旨在解决个人投资者面临的**信息过载**问题：将新闻、行情、财务、情绪与风险信号，通过多 Agent 协作转化为**结构化、可溯源、可流式呈现**的投研输出。

核心设计原则：

1. **Research 先于 Battle** — 四维子 Agent 并行完成独立研究后，再进入可选的多空辩论阶段（借鉴 [FinGenius](https://github.com/PbRQianJiang/FinGenius) 的 Research-Battle 范式）。
2. **工具隔离** — 各维度 Agent 仅调用本域数据工具，避免跨域信息污染（借鉴 [TradingAgents](https://github.com/TauricResearch/TradingAgents) 的角色边界设计）。
3. **规则与模型分工** — 快讯过滤、风控阈值由规则引擎承担；LLM 负责推理与自然语言生成。
4. **BYOK 隐私** — 大模型 API Key 由用户在本机浏览器配置，不经服务端持久化存储。

---

## 功能模块

| 模块 | 说明 |
|------|------|
| **智能对话** | 自然语言入口；个股/市场意图自动路由至多维投研；SSE 流式展示 Agent 全过程 |
| **四维投研** | 基本面、技术面、情绪面、筹码面独立 ReAct 子 Agent，工具集隔离、并行执行 |
| **多空辩论** | 设置中可开关；开启后追加看多/看空多轮辩论与裁判结论 |
| **新闻快讯** | 三层噪音过滤 + 持仓相关度排序；**3 秒 SLA**（规则引擎，不调用 LLM） |
| **持仓管理** | 成本、手数、盈亏、板块标签；行情定时刷新 |
| **风控体检** | 止损、集中度、VaR 等规则计算 + LLM 人话翻译 |
| **国际化** | 中/英界面切换；橙黑 / 酒红两套主题 |

![投研报告](docs/screenshots/research.png)

---

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│  Web Terminal (React 18 + Vite + TypeScript, :5174)    │
│  对话 · 快讯 · 持仓 · 风控  │  设置（BYOK / 辩论 / 语言） │
└───────────────────────────┬─────────────────────────────┘
                            │ REST + SSE
┌───────────────────────────▼─────────────────────────────┐
│  FastAPI (:8000) + SQLAlchemy + SQLite                 │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│  Orchestrator ([LangGraph](https://github.com/langchain-ai/langgraph)) │
│  意图路由 → research / debate / plan_execute / risk / direct │
└───────────────────────────┬─────────────────────────────┘
                            │
        ┌──────────┬────────┼────────┬──────────┐
        ▼          ▼        ▼        ▼          ▼
     News      Research  Market    Risk      Chat
     Agent     4×ReAct   Research  Agent     ReAct
     (规则)    +Debate   +Debate   (规则+LLM)
                            │
┌───────────────────────────▼─────────────────────────────┐
│  Data Layer：行情多源 · 新闻管道 · 缓存 · SQLite           │
└───────────────────────────────────────────────────────────┘
```

### 对话路由策略

| 用户设置 | 股票 / 市场相关问题 | 其他问题 |
|----------|---------------------|----------|
| 多空辩论 **开启** | 四维投研 → 多空辩论 → 裁判 | 直接回答 / 规划执行 |
| 多空辩论 **关闭** | 四维投研（无辩论） | 直接回答 / 规划执行 |
| 风控意图 + 有持仓 | 自动进入风控体检 | — |

### 四维投研子 Agent

| 维度 | 数据能力（示例） |
|------|------------------|
| 基本面 | 财务指标、估值分位、同行对比 |
| 技术面 | K 线、MACD/RSI、实时行情 |
| 情绪面 | 雪球热度、个股新闻 |
| 筹码面 | 龙虎榜、主力资金、股东户数、限售解禁 |

主要代码路径：`src/stockresearch/agents/research/agents/`、`stream.py`、`orchestrator/complexity.py`

---

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+

### 1. 启动后端

```bash
git clone https://github.com/Miles128/StockResearch.git
cd StockResearch
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
python3.12 -m uvicorn stockresearch.api.app:app --reload --host 127.0.0.1 --port 8000 --app-dir src
```

API 文档：<http://127.0.0.1:8000/docs>

### 2. 启动前端

```bash
cd web && npm install && npm run dev
```

浏览器访问 **<http://localhost:5174>**（建议使用 `localhost`，避免 IPv6 代理问题）。

### 3. 配置大模型

首次使用请在「设置」中填写 API Key 与模型信息（BYOK）。支持 OpenAI 兼容接口，例如：

- [DeepSeek](https://platform.deepseek.com/)
- [阿里云百炼 DashScope](https://help.aliyun.com/zh/model-studio/)（Base URL 填 `https://dashscope.aliyuncs.com/compatible-mode/v1`，系统自动补全 `/chat/completions`）

### Docker 一键启动

```bash
docker compose up --build
```

### 运行测试

```bash
pytest
ruff check src tests
```

---

## 部署

| 组件 | 说明 | 文档 |
|------|------|------|
| 前端 | Cloudflare Pages | [docs/deploy-cloudflare.md](docs/deploy-cloudflare.md) |
| 全栈 | Pages + Fly.io 自动部署 | [docs/deploy-auto.md](docs/deploy-auto.md) |

> 请勿在 Cloudflare / Fly 等平台的环境变量中写入 `LLM_API_KEY`。生产环境由用户浏览器 BYOK 传入。

---

## 环境变量

详见 [.env.example](.env.example)。

| 变量 | 说明 |
|------|------|
| `USE_MOCK_LLM` | `true` 时使用 Mock 回复，便于本地演示 |
| `USE_MOCK_MARKET_DATA` | `true` 时使用模拟行情数据 |
| `LLM_BASE_URL` | 服务端默认 Base URL（可为空，优先使用浏览器配置） |
| `LLM_API_KEY` | 服务端 Key（可选，生产建议留空） |
| `LLM_HTTP_PROXY` | HTTP 代理，如 `http://127.0.0.1:7890` |

---

## 对标开源项目

StockResearch 在架构与产品形态上参考了以下优秀开源项目，并向其作者与社区致谢：

| 项目 | 仓库 | 本项目借鉴点 |
|------|------|--------------|
| **TradingAgents** | [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) | 多 Agent 分工、多空辩论、研究经理与裁判流程；[LangGraph](https://github.com/langchain-ai/langgraph) 状态图编排 |
| **TradingAgents-CN** | [hsliuping/TradingAgents-CN](https://github.com/hsliuping/TradingAgents-CN) | A 股市场适配、国产大模型（通义千问 / DeepSeek 等）接入方案 |
| **FinGenius** | [PbRQianJiang/FinGenius](https://github.com/PbRQianJiang/FinGenius) | Research-Battle 双阶段：先独立研究、再进入辩论 |
| **Vibe-Trading** | [HKUDS/Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) | 多数据源降级、MCP 工具化、回测与研究记忆（规划中） |
| **FinRobot** | [AI4Finance-Foundation/FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) | 自动研报生成、感知-大脑-行动分层（报告导出规划中） |
| **FinGPT** | [AI4Finance-Foundation/FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) | 金融语料与情绪分析方向（情绪 Agent 增强规划中） |
| **QuantAgent** | [Y-Research-SBU/QuantAgent](https://github.com/Y-Research-SBU/QuantAgent) | 技术面可视化与 Web 交互参考 |
| **awesome-quant-ai** | [leoncuhk/awesome-quant-ai](https://github.com/leoncuhk/awesome-quant-ai) | 量化 AI Agent 生态索引与趋势跟踪 |

**差异化定位**：聚焦 A 股个人投资者的终端式体验；强调快讯 3 秒 SLA（零 LLM 成本）、BYOK 隐私与四维工具隔离，而非自动交易或荐股。

---

## 文档

- [产品需求文档 PRD v2.1（含路线图）](docs/PRD.md)
- [项目开发规划](docs/投小宝_项目开发规划.md)
- [架构说明（旧版归档）](docs/投小宝_PRD_Multi_Agent架构.md)

---

## 贡献

欢迎提交 Issue 与 Pull Request。开发前请阅读 PRD 中的路线图，避免与规划中的模块重复造轮子。

---

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE)。

---

## 免责声明

本产品所有 AI 生成内容仅供学习、研究与技术交流，**不构成任何投资建议**。证券市场有风险，投资决策请独立判断并自行承担后果。
