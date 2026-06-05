# StockResearch 产品需求文档（PRD）

> **版本 V2.0** · 2026-06-05 · Phase 1 MVP 已交付，进入体验优化与 Phase 2 规划  
> 仓库：<https://github.com/Miles128/StockResearch>

---

## 一、产品概述

### 1.1 一句话

**StockResearch** 是一款面向 A 股个人投资者的 Multi-Agent AI 投研终端——终端风 Web 界面，把快讯过滤、四维投研、可选多空辩论、风控体检和自然语言对话串成一条链路。

### 1.2 产品动机

个人投资者常见痛点不是「没信息」，而是「信息太多、看不完、理不清」。StockResearch 用多 Agent 分工 + 结构化输出，把「发生了什么 → 对我有何影响 → 风险在哪」压缩成可消费的卡片与流式过程，**不替代决策，只降低认知负担**。

### 1.3 目标用户

- 25–45 岁 A 股个人投资者
- 持仓 3–15 只，日常关注快讯与个股逻辑
- 愿意自备大模型 API Key（BYOK），接受「参考而非荐股」的产品边界

### 1.4 非目标（明确不做）

- 不提供买卖指令、目标价、仓位建议
- 不做实盘下单、券商对接（Phase 3 再评估）
- 不托管用户 API Key 至服务端持久化存储

---

## 二、当前版本（V1.x / Phase 1 MVP）

### 2.1 已交付能力

| 能力 | 状态 | 说明 |
|------|------|------|
| 智能对话 + SSE 流式 | ✅ | 展示 Agent 启动、维度分析、辩论轮次、裁判结论 |
| 市场/个股意图路由 | ✅ | 支持「A 股走势」「600519」等自然问法（含空格变体） |
| 四维 ReAct 子 Agent | ✅ | 基本面 / 技术面 / 情绪面 / 筹码面，工具隔离并行 |
| 多空辩论（可开关） | ✅ | 设置中默认开启；关闭时仅多维分析 |
| 大盘四维投研 | ✅ | 宏观 / 行业 / 技术 / 情绪 + 可选辩论 |
| 新闻快讯 | ✅ | 三层过滤 + 持仓相关度；**3 秒 SLA**，无 LLM |
| 风控体检 | ✅ | 规则引擎 + LLM 人话翻译 |
| 持仓管理 | ✅ | 成本、盈亏、板块 |
| BYOK 大模型 | ✅ | Key 存浏览器；支持 OpenAI 兼容（DeepSeek、百炼等） |
| DashScope URL 自动补全 | ✅ | Base URL `/v1` 自动追加 `/chat/completions` |
| 中英界面 | ✅ | 设置切换，localStorage 持久化 |
| 移动端窄屏优化 | ✅ | 顶栏仅文字 Tab 横排；对话区贴底布局 |
| Cloudflare Pages 前端 | ✅ | `stockresearch-4kx.pages.dev` |

### 2.2 核心用户流程

```
打开应用 → 设置大模型（首次）→ 可选开关「多空辩论」
    → 对话页提问（个股/大盘/闲聊/风控）
        → 路由：投研流 / 直接回答 / 规划执行 / 风控体检
        → SSE 流式展示过程 → 结论 + 卡片
```

### 2.3 分析模式说明（V2.0 变更）

**已移除**「简单分析 / 复杂分析」二次选择弹窗。

| 设置项 | 行为 |
|--------|------|
| 多空辩论 **开启** | 股票或市场相关问题 → 四维投研 + 多空辩论 + 裁判 |
| 多空辩论 **关闭** | 股票或市场相关问题 → 四维投研（无辩论） |
| 非市相关问题 | 直接回答或规划执行（多标的对比等） |
| 风控关键词 + 有持仓 | 自动走路控体检 |

---

## 三、系统架构

```
┌──────────────────────────────────────────────────────────┐
│  Web Terminal (React 18 + Vite + TypeScript)             │
│  对话 | 快讯 | 持仓 | 风控  ·  设置(BYOK/辩论/语言/主题)   │
└────────────────────────────┬─────────────────────────────┘
                             │ REST + SSE
┌────────────────────────────▼─────────────────────────────┐
│  FastAPI + SQLAlchemy + SQLite                           │
└────────────────────────────┬─────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────┐
│  Orchestrator (LangGraph)                                │
│  complexity router → research | market_research |        │
│    debate | market_debate | plan_execute | direct | risk │
└────────────────────────────┬─────────────────────────────┘
                             │
     ┌───────────┬───────────┼───────────┬───────────┐
     ▼           ▼           ▼           ▼           ▼
  News      Research     Market      Risk       Chat
  Agent      4×ReAct     Research    Agent      ReAct
  (规则)     +Debate     +Debate     (规则+LLM)  (兜底)
                             │
┌────────────────────────────▼─────────────────────────────┐
│  Data Layer：行情多源 · 新闻管道 · 本地缓存 · SQLite      │
└──────────────────────────────────────────────────────────┘
```

### 3.1 技术栈

| 层 | 选型 |
|----|------|
| 前端 | React 18, Vite, TypeScript, i18n (zh/en) |
| 后端 | FastAPI, SQLAlchemy, SQLite |
| Agent | LangGraph, 自研 ReAct 循环 |
| LLM | OpenAI 兼容 API，客户端 BYOK |
| 部署 | Cloudflare Pages（前端）, Fly.io（后端，待完善） |

---

## 四、Agent 规格（摘要）

### 4.1 新闻 Agent

- **SLA**：≤ 3 秒
- **LLM**：不使用
- **过滤**：标题党黑名单 → 信源权威加权 → 持仓/板块相关度排序

### 4.2 投研 Agent

**阶段一：四维并行 ReAct**

每个子 Agent 仅调用本维度工具，LLM 综合观测结果，输出 `DimensionResult`（评分、亮点、风险、数据来源）。

**阶段二：多空辩论（可选）**

- 看多 / 看空多轮交锋（SSE 流式）
- Research Manager 局势摘要
- 裁判 JSON 结论（bias / summary / divergence）
- 个股与大盘各有一套维度定义

### 4.3 风控 Agent

规则计算（回撤、集中度、VaR 等）+ LLM 翻译为可读叙述；支持流式多 Agent 风控辩论（持仓体检场景）。

### 4.4 对话路由

`complexity.py` 负责：

- `classify_research_scope`：识别个股 / 大盘意图（兼容 `A 股` 空格写法）
- `resolve_execution_mode`：结合 `enable_debate` 选择 research / debate / direct 等模式

---

## 五、非功能需求

| 项 | 目标 | 现状 |
|----|------|------|
| 快讯延迟 | ≤ 3s | ✅ |
| 投研完整流 | 深度优先，SSE 缓解等待 | ✅ |
| 测试覆盖 | 核心路由 / Agent / API | ✅ 113 cases |
| 合规 | 全输出带免责声明 | ✅ |
| 隐私 | API Key 不写入服务端 DB | ✅ |
| 移动体验 | 窄屏对话区最大化 | ✅ V2.0 |

---

## 六、竞品对标与差异化

| 项目 | 特点 | StockResearch 借鉴点 |
|------|------|------------------------|
| [TradingAgents](https://github.com/TauricResearch/TradingAgents) | 多 Agent 辩论、结构化输出、回测 | 辩论流程、裁判机制 |
| [TradingAgents-CN](https://github.com/hsliuping/TradingAgents-CN) | A 股 + 国产模型 | 本地数据源、DashScope |
| [FinGenius](https://github.com/PbRQianJiang/FinGenius) | Research-Battle 双阶段 | 先研究后辩论 |
| [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) | 多源数据降级、MCP、回测 | 数据层、工具生态 |
| [FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) | 自动研报生成 | 报告导出形态 |

**差异化**：A 股原生四维工具集 + 终端风体验 + BYOK 隐私 + 快讯 3 秒 SLA（无 LLM 成本）。

---

## 七、路线图

### Phase 1.5 — 体验与稳定性（1–2 周）【建议优先】

| 编号 | 功能 | 价值 |
|------|------|------|
| P1.5-1 | **结构化 Agent 输出**（Pydantic Schema 替代正则抽立场） | 减少解析失败，UI 更稳定 |
| P1.5-2 | **数据 Provider 抽象层**（新浪 → AkShare 自动降级链） | 行情稳定性；前端可展示当前数据源 |
| P1.5-3 | **后端稳定上线**（Fly / Railway / 阿里云轻量） | 前端演示站有可靠 API |
| P1.5-4 | **Token / 费用估算** | 单次投研成本可见，防止误烧额度 |

### Phase 2 — 差异化功能（1–2 月）

| 编号 | 功能 | 参考 |
|------|------|------|
| P2-1 | **投研报告导出**（Markdown / PDF） | FinRobot |
| P2-2 | **LangGraph Checkpoint** 断点续跑 | TradingAgents v0.2.4 |
| P2-3 | **决策记忆 + 事后反思**（reflect loop） | TradingAgents BM25 记忆 |
| P2-4 | **简化回测验证**（裁判信号 N 日 forward return） | 建立可信度，非荐股 |
| P2-5 | **技术图表嵌入**（K 线 + MACD/RSI） | QuantAgent |
| P2-6 | **定时简报 / 推送**（持仓相关早报） | 提升留存 |
| P2-7 | **行业 / 板块深度研究**（多轮 Plan-Execute） | 现有编排扩展 |

### Phase 3 — 生态与商业化（3–6 月）

| 编号 | 功能 | 说明 |
|------|------|------|
| P3-1 | **MCP Server**（暴露行情/投研/风控工具） | 对接 Claude Desktop / Cursor |
| P3-2 | **FinGPT 情绪 RAG / 轻量分类** | 降低情绪面 LLM 成本 |
| P3-3 | **小程序 / PWA 离线缓存** | 移动端触达 |
| P3-4 | **付费 tier**（高级数据源、更快模型路由） | 商业化探索 |
| P3-5 | **知识图谱**（产业链、供应链关联） | 行业研究增强 |

### 明确不在近期范围

- 实盘自动交易
- 服务端代持 API Key
- 明确买卖价位生成

---

## 八、合规与安全

1. 所有 AI 输出附带：**「以上内容由 AI 生成，仅供参考，不构成投资建议。」**
2. 产品不生成「买入 / 卖出 / 目标价」类指令性内容
3. 用户 API Key 仅存浏览器 localStorage，经请求头传给服务端即时使用，不落库
4. 日志不得打印完整 API Key

---

## 九、成功指标

| 阶段 | 指标 |
|------|------|
| Phase 1 | 对话 → 投研流完成率、SSE 中断率、测试全绿 |
| Phase 2 | 周活留存、报告导出次数、推送打开率 |
| Phase 3 | 付费转化（若启动）、MCP 调用量 |

**北极星（长期）**：周活跃用户中完成过一次「持仓相关投研」的占比。

---

## 十、附录：关键代码路径

| 模块 | 路径 |
|------|------|
| 对话路由 | `src/stockresearch/agents/orchestrator/complexity.py` |
| 流式编排 | `src/stockresearch/agents/orchestrator/stream.py` |
| 个股投研 SSE | `src/stockresearch/agents/research/stream.py` |
| 大盘投研 SSE | `src/stockresearch/agents/market/research_stream.py` |
| 四维 Agent | `src/stockresearch/agents/research/agents/` |
| 新闻过滤 | `src/stockresearch/agents/news/filter.py` |
| LLM 配置 | `src/stockresearch/core/llm_config.py` |
| 前端对话 | `web/src/App.tsx` |
| 分析设置 | `web/src/analysisSettings.ts` |
| i18n | `web/src/i18n.tsx` |

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| V1.0 | 2026-05-27 | 初版 PRD，Phase 1 规格 |
| V1.1 | 2026-05-27 | 四维 ReAct 拆分、新闻 SLA |
| V2.0 | 2026-06-05 | 移除简单/复杂分析弹窗；多空辩论设置；移动布局；DashScope 兼容；路线图重写 |
