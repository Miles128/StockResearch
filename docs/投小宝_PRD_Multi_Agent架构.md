# 投小宝 PRD（Product Requirement Document）

> 版本：**V1.1** | 日期：2026-05-27 | 状态：**Phase 1 MVP 已实现**  
> 仓库：https://github.com/Miles128/InvesBao

---

## 一、产品概述

### 1.1 产品定位

**投小宝（InvesBao）** 是一款面向 A 股个人投资者的 Multi-Agent AI 投研助手。以 **Bloomberg 风格 Web 终端** 为交互载体，整合快讯过滤、四维投研、智能风控与自然语言对话，帮助用户在信息过载中快速获得结构化参考。

### 1.2 当前交付范围（MVP）

| 能力 | 实现状态 | 说明 |
|------|----------|------|
| 对话路由 + SSE 流式 | ✅ | Intent Router → Orchestrator |
| 新闻 Agent（3 层过滤 + 3s SLA） | ✅ | 规则引擎，无 LLM |
| 投研 Agent（4 独立 ReAct 子 Agent） | ✅ | 工具隔离 + 辩论 + 裁判 |
| 风控 Agent | ✅ | 规则 + LLM 人话翻译 |
| 用户 / 持仓 / 自选股 | ✅ | SQLite |
| BBG 终端 UI | ✅ | Vite :5174 |

界面截图见 [README](../README.md)。

---

## 二、系统架构

### 2.1 总览

```
┌─────────────────────────────────────────────────────────┐
│  Web Terminal (React + Vite, port 5174)               │
│  F1 对话 | F2 行情 | F3 快讯 | F4 持仓 | F5 投研 | F6 风控 │
└───────────────────────────┬─────────────────────────────┘
                            │ REST + SSE
┌───────────────────────────▼─────────────────────────────┐
│  FastAPI (port 127.0.0.1:8000)                          │
│  routes: chat / news / research / risk / market / auth  │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│  Orchestrator (LangGraph)                               │
│  intent_router → news | research | risk | chat          │
└───────────────────────────┬─────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   News Agent         Research Agent        Risk Agent
   (filter.py)         (4× ReAct + debate)   (rules + LLM)
        │                   │                   │
        └───────────────────┴───────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│  Data Layer                                             │
│  AkShare · 新浪行情 · NewsPipeline · SQLite             │
└─────────────────────────────────────────────────────────┘
```

### 2.2 技术栈

| 层 | 选型 |
|----|------|
| 前端 | React 18, Vite, TypeScript |
| 后端 | FastAPI, SQLAlchemy, SQLite |
| Agent 编排 | LangGraph |
| LLM | OpenAI 兼容 API（DeepSeek 等），可 Mock |
| 行情/新闻 | AkShare, 新浪 Quote |

---

## 三、Agent 规格

### 3.1 新闻分析 Agent（实时 · 轻量）

**目标**：在 **3 秒内** 返回与用户相关的快讯卡片，不做长篇 LLM 推理。

| 属性 | 规格 |
|------|------|
| 触发 | 用户打开快讯页 / 对话意图 `news` / 手动刷新 |
| 输入 | SQLite 中已入库新闻 + 用户持仓/板块兴趣 |
| 输出 | `NewsItemOut` 列表（标题、摘要、情感、影响、关联标签） |
| SLA | **≤ 3 秒**（`asyncio.wait_for`） |
| LLM | **不使用** |

**三层噪音过滤**（`agents/news/filter.py`）：

| 层级 | 机制 | 实现 |
|------|------|------|
| L1 黑名单 | 标题含「暴涨」「惊爆」等标题党 → **丢弃** | `NEWS_BLACKLIST_KEYWORDS` |
| L2 信源权威 | 财联社 0.95、证券时报 0.92、东方财富 0.78… | `NEWS_SOURCE_AUTHORITY` |
| L3 相关度 | 持仓 1.0 > 板块 0.85 > 大盘 0.65 | `classify_news` + 加权排序 |

综合得分：`authority × relevance × impact_weight`，降序取 Top N。

入库管道（`data/pipeline/news.py`）在 ingest 阶段同样应用 L1 + 相关度分类。

---

### 3.2 投研分析 Agent（深度 · 流式）

**目标**：对单只股票输出四维评分 + 多空辩论 + 裁判结论，支持 SSE 真流式输出。

#### 3.2.1 四维独立 ReAct 子 Agent

> **V1.1 变更**：子 Agent 从单一 `runner.py` 拆分为 **4 个独立模块**，各持隔离工具集，经 `react.py` 统一执行 ReAct 循环。

| 子 Agent | 模块 | 隔离工具 |
|----------|------|----------|
| 基本面 | `agents/fundamental.py` | 财务、估值、同行 |
| 技术面 | `agents/technical.py` | K 线指标、实时行情 |
| 情绪面 | `agents/sentiment.py` | 雪球热度、个股新闻 |
| 筹码面 | `agents/chips.py` | 龙虎榜、资金流、股东户、解禁 |

**ReAct 循环**（每维一次）：

```
for tool in agent.tools:
    observations[tool.name] = await tool.run(ctx)
analysis = await llm.complete(system_prompt, format(observations))
return agent.build(observations, analysis)
```

四维 **并行** 执行（`asyncio.gather`），随后进入辩论阶段。

#### 3.2.2 多空辩论

| 步骤 | 角色 | 输出 |
|------|------|------|
| Round 1–N | 看多 / 看空 Agent | 逐轮论点（SSE 流式） |
| Manager | 研究经理 | 局势摘要 |
| Judge | 裁判 Agent | JSON：bias / summary / divergence |

#### 3.2.3 输出结构

`ResearchReportOut`：四维 `DimensionResult`、综合分、bias、summary、`DebateResult`。

---

### 3.3 风控 Agent（实时）

| 维度 | 规则示例 | 预警 |
|------|----------|------|
| 个股止损 | 成本回撤 | 8% 黄 / 15% 红 |
| 集中度 | 单板块占比 | >40% 提示 |
| 黑天鹅 | ST、立案、退市关键词 | 即时命中 |

规则引擎产出结构化告警，LLM 仅做人话翻译（可 Mock）。

---

### 3.4 对话 Agent（入口）

| 职责 | 说明 |
|------|------|
| 意图识别 | `news` / `research` / `risk` / `chat` / `composite` |
| 任务分发 | Orchestrator 路由至对应 Agent |
| 流式呈现 | SSE `StreamFeed` 组件展示 Agent 过程 |

---

## 四、用户与数据

### 4.1 核心用户

25–45 岁 A 股个人投资者，持仓 3–15 只，需要「发生了什么 → 对我有何影响 → 风险如何」的快捷路径。

### 4.2 用户数据

- 注册 / 登录（JWT）
- 持仓：代码、成本、数量、板块
- 新闻兴趣：持仓股 + 自选板块

---

## 五、非功能需求

| 项 | 目标 | 现状 |
|----|------|------|
| 新闻 feed 延迟 | ≤ 3s | ✅ `NEWS_FEED_SLA_SEC = 3.0` |
| 投研完整报告 | 深度优先 | ~2min（真 LLM + 辩论），SSE 缓解体感 |
| 前端端口 | 5174 | ✅ 代理 127.0.0.1:8000 |
| 测试 | pytest 全绿 | ✅ 82+ cases |

---

## 六、路线图

| 阶段 | 内容 |
|------|------|
| **Phase 1（当前）** | MVP：四维 ReAct、新闻过滤、风控、BBG UI |
| Phase 2 | 推送 / 定时简报、知识图谱、多轮行业研究 |
| Phase 3 | 小程序 / App、实盘对接、付费 tier |

---

## 七、合规

所有 AI 输出必须附带免责声明：**「以上内容由 AI 生成，仅供参考，不构成投资建议。」**

产品不得生成明确的买卖指令；投研输出以评分与多空论据为主，决策权归用户。

---

## 附录：关键代码路径

| 模块 | 路径 |
|------|------|
| 新闻过滤 | `src/invesbao/agents/news/filter.py` |
| 新闻 Agent | `src/invesbao/agents/news/agent.py` |
| ReAct 引擎 | `src/invesbao/agents/research/react.py` |
| 四维 Agent | `src/invesbao/agents/research/agents/` |
| 投研编排 | `src/invesbao/agents/research/runner.py` |
| 投研 SSE | `src/invesbao/agents/research/stream.py` |
| 编排图 | `src/invesbao/agents/orchestrator/graph.py` |
| 前端 | `web/src/App.tsx` |
