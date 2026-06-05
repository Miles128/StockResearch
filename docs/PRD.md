# StockResearch 产品需求文档（PRD）

> **版本 V2.3** · 2026-06-05  
> **状态**：Phase 1 已交付 · Phase 1.5 进行中（部分项已落地）  
> **仓库**：[github.com/Miles128/StockResearch](https://github.com/Miles128/StockResearch)

---

## 一、产品概述

### 1.1 产品定义

**StockResearch** 是一款面向 A 股个人投资者的 Multi-Agent AI 投研终端。产品以 Bloomberg 风格 Web 界面为交互载体，整合自然语言对话、四维投研、可选多空辩论、持仓风控与快讯过滤，帮助用户在信息过载环境下获得**结构化、可溯源、合规边界清晰**的研究参考。

### 1.2 要解决的问题

| 用户痛点 | 产品应对 |
|----------|----------|
| 信息来源分散、噪音高 | 新闻三层过滤 + 持仓相关度排序（3 秒 SLA） |
| 单模型结论缺乏对抗性检验 | 可选多空辩论 + 裁判综合 |
| 投研维度混杂、难以追溯 | 四维 ReAct 子 Agent，工具集隔离 |
| 专业风控指标难以理解 | 规则引擎计算 + LLM 人话翻译 |
| 不愿将 API Key 托管给第三方 | 浏览器 BYOK，Key 不落服务端数据库 |

### 1.3 目标用户

- A 股个人投资者，持仓 3–15 只
- 具备基础证券知识，需要「研究参考」而非「买卖指令」
- 可自备 OpenAI 兼容大模型 API（DeepSeek、通义千问等）

### 1.4 产品边界（非目标）

- ❌ 不生成买入/卖出/目标价等指令性内容
- ❌ 不提供实盘下单、券商接口（远期单独评估）
- ❌ 不在服务端长期存储用户 API Key
- ❌ 不承诺投资收益或胜率

---

## 二、已交付能力（Phase 1 / V1.x）

| 编号 | 能力 | 状态 | 说明 |
|------|------|------|------|
| F-01 | 智能对话 + SSE 流式 | ✅ | 实时展示 Agent 启动、维度输出、辩论、裁判 |
| F-02 | 个股四维 ReAct 投研 | ✅ | 基本面/技术面/情绪面/筹码面，并行执行 |
| F-03 | 大盘四维投研 | ✅ | 宏观/行业/技术/情绪 |
| F-04 | 多空辩论（可开关） | ✅ | 设置控制；默认开启 |
| F-05 | 市场/个股意图路由 | ✅ | 支持自然问法（含「A 股」空格变体） |
| F-06 | 新闻快讯 | ✅ | 三层过滤；≤3s；无 LLM |
| F-07 | 持仓管理 | ✅ | 成本、盈亏、板块 |
| F-08 | 风控体检 | ✅ | 规则 + LLM 翻译；支持流式多 Agent |
| F-09 | BYOK 大模型 | ✅ | 浏览器配置；DashScope URL 自动补全 |
| F-10 | 中英界面 + 主题 | ✅ | localStorage 持久化 |
| F-11 | 移动端窄屏布局 | ✅ | 文字 Tab 横排；对话区满屏 |
| F-12 | 生产部署 | ⏳ | 待定（短期仅本地/Docker 开发） |
| F-13 | 投研历史 + Markdown 导出 | ✅ | 流式投研落库；设置页可导出 |
| F-14 | 数据源降级可视化 | ✅ | `/market/data-status`；顶栏展示行情源 |
| F-15 | 股票歧义确认 | ✅ | 低置信度时卡片点选后再分析 |
| F-16 | Tushare Pro（可选） | ✅ | 设置 → 数据源；BYOT；AkShare 失败时补估值 |
| F-17 | 设置页 F5 + 分页 | ✅ | 通用/数据源/大模型/分析/报告/关于 |
| F-18 | 真实雪球/东财情绪 | ✅ | 替换伪热度；东财新闻 API 直连 |

### 2.1 分析模式（V2.0 起）

已取消「简单分析 / 复杂分析」二次确认。统一由设置项 **「开启多空辩论」** 控制：

| 多空辩论 | 股票/市场类问题 | 其他问题 |
|----------|-----------------|----------|
| 开启 | 四维投研 + 三轮多空 + 投票 + Research Manager + 裁判总结 | 直接回答 / Plan-Execute |
| 关闭 | 四维投研（无辩论） | 直接回答 / Plan-Execute |

### 2.2 投研流式呈现（V2.2）

- 四维各一卡片（开始/完成/正文），辩论须等四维全部完成
- 辩论轮次支持「展开详述」展示全文（不再 220 字截断）
- 免责声明：顶栏小字常驻；研究轮次结束一次展示；子 Agent 正文内剥离

---

## 三、系统架构

```
Web Terminal (React + Vite)
        │ REST + SSE
FastAPI + SQLite
        │
LangGraph Orchestrator
  ├── complexity router
  ├── research / market_research
  ├── debate / market_debate
  ├── plan_execute
  ├── risk
  └── direct (ReAct chat)
        │
Data Layer (行情 · 新闻 · 情绪 · 可选 Tushare)
```

### 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18, TypeScript, Vite |
| 后端 | FastAPI, SQLAlchemy |
| Agent | LangGraph, 自研 ReAct |
| 存储 | SQLite |
| 行情 | 新浪 → AkShare 降级 |
| 新闻/情绪 | AkShare、东财搜索 API、雪球热榜 |
| 可选数据 | Tushare Pro（用户 Token，BYOT） |
| LLM | OpenAI 兼容 API（BYOK） |
| 部署 | **待定**（短期不部署；本地 `uvicorn` + `npm run dev`） |

---

## 四、对标开源项目与借鉴关系

本项目在设计与演进中明确参考以下开源生态，并向对应社区致谢。

### 4.1 核心对标

#### [TradingAgents](https://github.com/TauricResearch/TradingAgents)（Tauric Research）

- **定位**：模拟交易公司分工的多 Agent LLM 框架（基本面/情绪/新闻/技术 → 交易员/风控）。
- **借鉴**：多空辩论流程、裁判综合、LangGraph 模块化编排。
- **差异**：StockResearch 聚焦 A 股数据源与终端式体验；强调 BYOK 与快讯规则引擎。
- **待引入**（见路线图）：结构化 Pydantic 输出、Checkpoint 断点续跑、决策记忆与回测 CLI（v0.2.4+ 特性）。

#### [TradingAgents-CN](https://github.com/hsliuping/TradingAgents-CN)

- **定位**：TradingAgents 的 A 股与国产大模型适配版。
- **借鉴**：DashScope / DeepSeek 接入、A 股语料与工具链本地化思路。
- **差异**：本产品前端自研终端 UI，后端工具集按四维 ReAct 重新组织。

#### [FinGenius](https://github.com/PbRQianJiang/FinGenius)

- **定位**：Research-Battle 双阶段投研。
- **借鉴**：**先完成四维独立研究，再进入 Battle**——避免信息不全即辩论。
- **差异**：Battle 阶段可选关闭；大盘与个股各有独立维度定义。

#### [LangGraph](https://github.com/langchain-ai/langgraph)

- **定位**：有状态 Multi-Agent 工作流框架。
- **借鉴**：Orchestrator 状态图、条件路由、可恢复执行（规划中）。
- **应用**：`orchestrator/graph.py`、`stream.py`。

### 4.2 扩展对标

#### [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading)

- 多数据源自动降级、MCP Server、跨市场回测、持久研究记忆。
- **规划对应**：P1.5 数据 Provider 抽象、P3 MCP 暴露、P2 简化回测验证。

#### [FinRobot](https://github.com/AI4Finance-Foundation/FinRobot)

- 自动权益研报、感知-大脑-行动分层、多源 LLM 调度。
- **规划对应**：P2 投研报告 Markdown/PDF 导出。

#### [FinGPT](https://github.com/AI4Finance-Foundation/FinGPT)

- 金融 LLM 微调、情绪分析、数据驱动训练管线。
- **规划对应**：P3 情绪 Agent RAG / 轻量分类，降低 LLM 成本。

#### [QuantAgent](https://github.com/Y-Research-SBU/QuantAgent)

- 技术面多 Agent + 交互图表 + Web 界面。
- **规划对应**：P2 K 线/MACD/RSI 前端可视化。

#### [awesome-quant-ai](https://github.com/leoncuhk/awesome-quant-ai)

- 量化 AI Agent 索引与趋势汇总。
- **用途**：持续跟踪社区最佳实践，校准路线图优先级。

### 4.3 差异化总结

| 维度 | 主流开源项目常见做法 | StockResearch 选择 |
|------|----------------------|-------------------|
| 市场 | 美股 / 多市场 | **A 股原生**工具与语料 |
| 交互 | CLI / Notebook | **终端风 Web** + 移动端 |
| 快讯 | 常依赖 LLM 摘要 | **规则引擎 3s SLA** |
| 隐私 | 服务端配 Key | **浏览器 BYOK** |
| 合规 | 各异 | **强制免责声明**，不输出买卖指令 |

---

## 五、未来开发路线图

### Phase 1.5 — 稳定性与可信度（进行中）

> 目标：降低生产环境失败率，提升投研输出可解析性与数据可信度。

| ID | 需求 | 状态 | 验收标准 |
|----|------|------|----------|
| P1.5-1 | 结构化 Agent 输出 | ✅ | 裁判/投票 Pydantic；`ResearchJudgeOut` 等 |
| P1.5-2 | 数据 Provider 抽象 | ✅ | 行情降级链、`data-status` API、顶栏徽章 |
| P1.5-3 | 情绪/新闻真实采集 | ✅ | 雪球热榜 + 东财新闻；去除伪热度下限 |
| P1.5-4 | Tushare 可选接入 | ✅ | 设置页 Token；请求头透传；估值降级 |
| P1.5-5 | 投研落库与导出 | ✅ | 历史列表 + Markdown 导出 |
| P1.5-6 | 生产部署 | ⏳ | 待定 |
| P1.5-7 | Token 成本可见 | ⏳ | 单次投研 token/费用估算 |
| P1.5-8 | E2E 冒烟 CI | 🔄 | 核心路径自动化（当前 pytest 136） |

### Phase 2 — 体验深化（预计 1–2 月）

> 目标：形成可留存、可分享、可验证的研究产出。

| ID | 需求 | 验收标准 | 参考项目 |
|----|------|----------|----------|
| P2-1 | 投研报告导出 | Markdown ✅；PDF 待做 | FinRobot |
| P2-2 | LangGraph Checkpoint | 长任务中断后可从最近节点恢复 | TradingAgents |
| P2-3 | 决策记忆 + Reflect | 历史投研日志；事后反思写入可检索记忆 | TradingAgents BM25 |
| P2-4 | 信号回测摘要 | 裁判偏多/偏空信号 N 日 forward return 统计（非荐股） | Vibe-Trading |
| P2-5 | 技术图表组件 | 个股页嵌入 K 线 + MACD/RSI | QuantAgent |
| P2-6 | 定时简报 | 持仓相关早报/收盘摘要；推送通道预留 | — |
| P2-7 | 行业/板块研究 | 多轮 Plan-Execute 深度行业报告 | FinGenius 扩展 |

### Phase 3 — 生态扩展（预计 3–6 月）

> 目标：从单一产品延伸至可集成的投研基础设施。

| ID | 需求 | 验收标准 | 参考项目 |
|----|------|----------|----------|
| P3-1 | MCP Server | 暴露行情、投研、风控工具；支持 Claude Desktop / Cursor | Vibe-Trading |
| P3-2 | 情绪 RAG | A 股情绪语料检索增强；可选轻量分类模型 | FinGPT |
| P3-3 | PWA / 小程序 | 移动端触达；离线缓存只读报告 | — |
| P3-4 | 知识图谱 | 产业链/供应链关联探索 | — |
| P3-5 | 商业化探索 | 高级数据源、更快速度档（需合规评审） | — |

### 明确排除项

- 自动实盘交易与订单执行
- 服务端代持用户 API Key
- 生成具体买卖价位、仓位比例建议

---

## 六、非功能需求

| 类别 | 指标 | 当前 |
|------|------|------|
| 性能 | 快讯 feed ≤ 3s | ✅ |
| 性能 | 投研流式首字节 < 5s（依赖 LLM） | 待量化 |
| 可靠性 | 核心 pytest 通过 | ✅ 136 cases |
| 安全 | API Key 不落库 | ✅ |
| 合规 | 全输出含免责声明 | ✅ |
| 可用性 | 窄屏对话区可用 | ✅ |
| 可维护性 | 路由/Agent 单测覆盖 | 持续加强 |

---

## 七、合规与安全

1. 研究类对话轮次结束须展示：**「以下内容由 AI 生成，仅供参考，不构成投资建议。」**（顶栏小字常驻；子流程正文内不重复）
2. 禁止输出「建议买入/卖出」「目标价」「建仓比例」等指令性表述。
3. API Key 仅存用户浏览器 `localStorage`，经 HTTP 头传递，服务端不写入数据库。
4. 日志与错误信息禁止打印完整 Key。
5. 产品对外宣传不得承诺收益。

---

## 八、成功指标

| 阶段 | 核心指标 |
|------|----------|
| Phase 1 | 投研流完成率、SSE 中断率、单元/集成测试通过率 |
| Phase 1.5 | 结构化输出解析成功率、数据源降级命中率 |
| Phase 2 | 周留存、报告导出次数、简报打开率 |
| Phase 3 | MCP 调用量、第三方集成数 |

**北极星指标**：每周活跃用户中，完成至少一次「与持仓相关的投研/风控」行为的占比。

---

## 九、附录

### 9.1 关键代码路径

| 模块 | 路径 |
|------|------|
| 意图路由 | `src/stockresearch/agents/orchestrator/complexity.py` |
| 流式编排 | `src/stockresearch/agents/orchestrator/stream.py` |
| 个股投研 | `src/stockresearch/agents/research/stream.py` |
| 大盘投研 | `src/stockresearch/agents/market/research_stream.py` |
| 新闻过滤 | `src/stockresearch/agents/news/filter.py` |
| LLM 配置 | `src/stockresearch/core/llm_config.py` |
| 前端 | `web/src/App.tsx`、`SettingsPanel.tsx`、`streamEvents.ts` |
| 数据源 | `data/providers/market.py`、`news.py`、`tushare_financial.py` |
| 初版规划 | `docs/DEVELOPMENT_PLAN.md`（基线，不随迭代改写） |

### 9.2 文档索引

| 文档 | 用途 |
|------|------|
| [PRD.md](./PRD.md) | **现行**产品需求与路线图（本文档） |
| [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md) | **初版**工程规划基线（2026-05-27） |

### 9.3 修订记录

| 版本 | 日期 | 摘要 |
|------|------|------|
| V1.0 | 2026-05-27 | 初版 PRD |
| V1.1 | 2026-05-27 | 四维 ReAct 拆分 |
| V2.0 | 2026-06-05 | 多空辩论设置、移动布局、路线图 |
| V2.1 | 2026-06-05 | 开源对标与路线图细化 |
| V2.2 | 2026-06-05 | 对齐现网：Phase 1.5 进展、Tushare、设置 F5、文档收敛为两份 |
| V2.3 | 2026-06-05 | 部署待定；全局指数 Ticker、对话空状态、持仓摘要、新闻分组/板块、风控引导 |
