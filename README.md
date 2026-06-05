# StockResearch

[English](README.en.md) · [产品 PRD](docs/PRD.md)

面向 A 股个人投资者的 **本机 Multi-Agent AI 投研终端**。Bloomberg 风格 Web 界面，LangGraph 编排专用 Agent，**单用户、SQLite、浏览器 BYOK**——不注册、不上线、不收费。

> **免责声明**：所有 AI 输出仅供学习与研究参考，不构成任何投资建议。

[![Tests](https://img.shields.io/badge/tests-138%20passed-brightgreen)](.)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

| 链接 | 地址 |
|------|------|
| 源码 | [github.com/Miles128/StockResearch](https://github.com/Miles128/StockResearch) |
| PRD | [docs/PRD.md](docs/PRD.md) |

---

## 界面预览

### 对话（F1）

自然语言入口，SSE 流式展示四维投研、多空辩论与裁判全过程；顶栏显示 Token 用量与行情数据源。

![对话](docs/screenshots/chat.png)

### 新闻（F2）

三层规则过滤快讯，按持仓 / 板块 / 市场分组；可订阅关注板块。

![新闻](docs/screenshots/news.png)

### 持仓（F3）

录入成本与手数，实时盈亏、行业集中度摘要，一键跳转个股分析。

![持仓](docs/screenshots/portfolio.png)

### 风控（F4）

组合 Sharpe、VaR、集中度等指标 + 规则告警与 LLM 人话解读。

![风控](docs/screenshots/risk.png)

### 设置（F5）

BYOK 大模型、可选 Tushare Token、多空辩论开关、投研报告导出与关于页。

![设置](docs/screenshots/settings.png)

---

## 产品定位

StockResearch 是**长期开源 MVP**：跑在你自己电脑上的投研工作台，不是公网 SaaS。

| 原则 | 说明 |
|------|------|
| **本机优先** | `venv` + SQLite + `localhost`，无 Docker/Redis/Postgres 依赖 |
| **单用户** | 固定本地用户 `mvp`，无需登录 |
| **Research 先于 Battle** | 四维独立研究完成后，再进入可选多空辩论（[FinGenius](https://github.com/PbRQianJiang/FinGenius) 范式） |
| **工具隔离** | 各维度 Agent 仅调用本域工具（[TradingAgents](https://github.com/TauricResearch/TradingAgents) 边界） |
| **规则与模型分工** | 快讯/风控阈值走规则；LLM 负责推理与生成 |
| **BYOK** | API Key 仅存浏览器，不经服务端数据库 |

---

## 功能一览

| 模块 | 说明 |
|------|------|
| 智能对话 | 个股/市场意图路由；歧义股票卡片确认 |
| 四维投研 | 基本面、技术面、情绪面、筹码面 ReAct 并行 |
| 多空辩论 | 设置中可开关 |
| 新闻快讯 | ≤3s SLA，零 LLM |
| 持仓管理 | 成本、盈亏、板块、定时刷新 |
| 风控体检 | VaR、回撤、集中度 + AI 解读 |
| 国际化 | 中/英界面；橙黑 / 酒红主题 |

---

## 架构

```
浏览器 (:5174)  ──REST/SSE──▶  FastAPI (:8000) + SQLite
                                    │
                              LangGraph Orchestrator
                                    │
                    行情 · 新闻 · 情绪 · 可选 Tushare
```

---

## 快速开始

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
pytest          # 138 tests
cd web && npm run build
```

---

## 环境变量

见 [.env.example](.env.example)。常用项：

| 变量 | 说明 |
|------|------|
| `USE_MOCK_LLM` | `true` 时 Mock 回复，便于无 Key 演示 |
| `USE_MOCK_MARKET_DATA` | `true` 时模拟行情 |
| `LLM_HTTP_PROXY` | 本机访问 API 的代理，如 `http://127.0.0.1:7890` |

LLM Key 优先使用浏览器设置，`.env` 中的 `LLM_API_KEY` 可留空。

---

## 文档

- [PRD v3.0（单用户本机）](docs/PRD.md)
- [初版开发规划（历史基线）](docs/DEVELOPMENT_PLAN.md)
- [English README](README.en.md)

---

## 贡献

欢迎 Issue 与 PR。请先阅读 PRD 路线图，避免重复实现已规划模块。

---

## 许可证

MIT — 见 [LICENSE](LICENSE)。

---

## 免责声明

本产品所有 AI 生成内容仅供学习、研究与技术交流，**不构成任何投资建议**。证券市场有风险，投资决策请独立判断并自行承担后果。
