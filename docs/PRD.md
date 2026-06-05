# StockResearch 产品需求文档（PRD）

> **版本 V3.0** · 2026-06-05  
> **定位**：单用户、本机运行、长期开源 MVP  
> **状态**：Phase 1 / 1.5 已交付 · Phase 2 待启动  
> **仓库**：[github.com/Miles128/StockResearch](https://github.com/Miles128/StockResearch)  
> **English README**：[README.en.md](../README.en.md)

---

## 一、产品是什么

### 1.1 一句话

**StockResearch** 是跑在你自己电脑上的 A 股 Multi-Agent 投研终端：Bloomberg 风格 Web UI + LangGraph 编排 + SQLite 本地库，**不注册、不登录、不上线、不收费**。

### 1.2 为谁做

| 角色 | 说明 |
|------|------|
| **主用户** | 开发者本人：A 股个人投资者，持仓约 3–15 只 |
| **次要用户** | 克隆仓库自行部署的开源使用者（同样本机自用） |
| **不是谁** | 公网多租户 SaaS 用户、付费订阅客户 |

### 1.3 解决什么问题

| 痛点 | 应对 |
|------|------|
| 信息噪音大 | 新闻三层规则过滤，feed ≤ 3s，零 LLM |
| 单模型结论片面 | 可选四维投研 + 多空辩论 + 裁判 |
| 维度混杂难追溯 | 基本面/技术面/情绪面/筹码面 ReAct 隔离 |
| 风控指标难懂 | 规则引擎 + LLM 人话翻译 |
| 不愿托管 API Key | 浏览器 BYOK，服务端不落库 |

### 1.4 永久不做

- 用户注册、登录、多租户、权限体系
- 公网 SaaS、商业化收费、代售数据源
- 自动实盘下单、具体买卖价位/仓位建议
- 服务端长期存储用户 LLM / Tushare Key

---

## 二、运行形态（单用户本机）

```
你的浏览器 (localhost:5174)
  │  BYOK：API Key 存 localStorage
  │  REST + SSE
  ▼
本机 FastAPI (127.0.0.1:8000)
  │  固定单用户 mvp（无 JWT）
  ▼
SQLite (./stockresearch.db)
  │  持仓 · 对话 · 投研历史 · 快讯
  ▼
LangGraph 多 Agent + 行情/新闻数据层
```

### 2.1 启动方式

```bash
# 终端 1 — 后端
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn stockresearch.api.app:app --reload --host 127.0.0.1 --port 8000 --app-dir src

# 终端 2 — 前端
cd web && npm install && npm run dev
# 打开 http://localhost:5174
```

### 2.2 用户与数据

- 数据库仅一条逻辑用户 `mvp`，首次启动自动创建
- 所有持仓、对话、投研记录归属该用户，**无账号切换**
- 换电脑 = 换一份 `stockresearch.db`（或重新录入持仓）

### 2.3 密钥与数据源

| 类型 | 存放位置 | 说明 |
|------|----------|------|
| LLM API Key | 浏览器 `localStorage` | 设置页 BYOK；请求经 Header 透传 |
| Tushare Token | 浏览器 `localStorage` | 可选 BYOT；估值降级补全 |
| `.env` | 本机文件 | 仅开发默认项；`USE_MOCK_*` 便于无 Key 演示 |

---

## 三、已交付能力

| 编号 | 能力 | 说明 |
|------|------|------|
| F-01 | 智能对话 + SSE 流式 | Agent 全过程可视化；顶栏 Token 费用 |
| F-02 | 个股四维 ReAct 投研 | 基本面/技术面/情绪面/筹码面并行 |
| F-03 | 大盘四维投研 | 宏观/行业/技术/情绪 |
| F-04 | 多空辩论（可开关） | 设置项控制，默认开启 |
| F-05 | 意图路由 | 自然语言；歧义股票卡片确认 |
| F-06 | 新闻快讯 | 三层过滤；板块订阅；分组展示 |
| F-07 | 持仓管理 | 成本/盈亏/板块；摘要与行业集中度 |
| F-08 | 风控体检 | Sharpe/VaR/集中度 + LLM 解读 |
| F-09 | BYOK 大模型 | DeepSeek / DashScope 等 OpenAI 兼容 |
| F-10 | 中英界面 + 双主题 | localStorage 持久化 |
| F-11 | 窄屏布局 | 移动 Tab + 满屏对话 |
| F-12 | 投研历史 + Markdown 导出 | 设置页导出 |
| F-13 | 数据源降级可视化 | 顶栏行情源徽章 |
| F-14 | Tushare Pro（可选） | BYOT |
| F-15 | 全局指数 Ticker | 顶栏指数；隐藏刷新 |
| F-16 | 设置分页 | 通用/数据源/模型/分析/报告/关于 |

### 3.1 分析模式

由 **「开启多空辩论」** 唯一控制（无简单/复杂二次确认）：

| 辩论 | 股票/市场问题 | 其他问题 |
|------|---------------|----------|
| 开 | 四维投研 → 辩论 → 裁判 | 直接答 / Plan-Execute |
| 关 | 四维投研（无辩论） | 直接答 / Plan-Execute |

### 3.2 界面模块（F1–F5）

| 快捷键 | 模块 | 核心能力 |
|--------|------|----------|
| F1 | 对话 | 自然语言投研入口、流式 Multi-Agent |
| F2 | 新闻 | 持仓/板块/市场分组快讯 |
| F3 | 持仓 | 录入、盈亏、一键分析 |
| F4 | 风控 | 组合体检、VaR、告警 |
| F5 | 设置 | BYOK、辩论开关、报告导出 |

---

## 四、系统架构

```
web/src/
  App.tsx          # 壳：状态、chrome、ticker
  ChatPanel.tsx    # F1
  NewsPanel.tsx    # F2
  PortfolioPanel.tsx
  RiskPanel.tsx
  SettingsPanel.tsx

src/stockresearch/
  api/             # FastAPI 路由
  agents/          # LangGraph + ReAct
  data/providers/  # 行情、新闻、Tushare
  services/        # local_user, cache, news_interests
  db/              # SQLite models
```

### 技术栈

| 层级 | 选型 |
|------|------|
| 前端 | React 18, TypeScript, Vite |
| 后端 | FastAPI, SQLAlchemy |
| Agent | LangGraph, 自研 ReAct |
| 存储 | SQLite（单文件） |
| 缓存 | 进程内内存（无 Redis） |
| 行情 | 新浪 → AkShare 降级 |
| LLM | OpenAI 兼容 API（BYOK） |

---

## 五、路线图

### Phase 1 / 1.5 — 已完成

核心终端、四维投研、流式 UI、BYOK、Tushare 可选、投研导出、Token 成本、138 pytest + 前端 build CI。

### Phase 2 — 体验深化（当前）

> 目标：个人可留存、可分享、可验证的研究产出（仍本机运行）。

| ID | 需求 | 验收 |
|----|------|------|
| P2-1 | PDF 报告导出 | Markdown 已有；补 PDF |
| P2-2 | 技术图表 | 个股 K 线 + MACD/RSI 组件 |
| P2-3 | 行业深度研究 | Plan-Execute 多轮板块报告 |
| P2-4 | 持仓简报 | 手动生成早报/收盘摘要（无推送基础设施） |
| P2-5 | 信号回测摘要 | 裁判信号 N 日 forward return（非荐股） |
| P2-6 | LangGraph Checkpoint | 长任务断点续跑（低优先级） |
| P2-7 | 决策记忆 | 历史投研检索（低优先级） |

### Phase 3 — 可选探索

| ID | 需求 |
|----|------|
| P3-1 | MCP Server（Cursor / Claude Desktop 调工具） |
| P3-2 | 情绪 RAG |
| P3-3 | PWA 只读报告缓存 |

---

## 六、非功能需求

| 类别 | 指标 | 现状 |
|------|------|------|
| 性能 | 快讯 feed ≤ 3s | ✅ |
| 可靠性 | pytest | ✅ 138 |
| 隐私 | Key 不落库 | ✅ |
| 合规 | 免责声明 | ✅ |
| 可维护性 | 面板拆分、单测 | ✅ 持续 |

---

## 七、合规

1. 研究轮次结束展示：**「以下内容由 AI 生成，仅供参考，不构成投资建议。」**
2. 禁止输出买入/卖出/目标价/建仓比例等指令。
3. API Key 仅浏览器存储，日志不得打印完整 Key。

---

## 八、成功指标（个人自用）

| 指标 | 含义 |
|------|------|
| 投研完成率 | 发起个股/大盘分析后流式正常结束的比例 |
| 持仓关联使用 | 有持仓时，周均 ≥1 次投研或风控 |
| 导出次数 | Markdown/PDF 报告导出（Phase 2） |

---

## 九、对标与致谢

参考 [TradingAgents](https://github.com/TauricResearch/TradingAgents)、[FinGenius](https://github.com/PbRQianJiang/FinGenius)、[TradingAgents-CN](https://github.com/hsliuping/TradingAgents-CN)、[LangGraph](https://github.com/langchain-ai/langgraph) 等开源生态；差异化在于 **A 股终端体验 + 规则快讯 + 本机 BYOK**，而非自动交易或 SaaS。

---

## 十、附录

### 文档

| 文件 | 用途 |
|------|------|
| [PRD.md](./PRD.md) | 本文档（现行） |
| [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md) | 初版工程基线（历史参考） |
| [README.md](../README.md) | 中文说明 |
| [README.en.md](../README.en.md) | English readme |

### 修订记录

| 版本 | 日期 | 摘要 |
|------|------|------|
| V3.0 | 2026-06-05 | **按单用户本机 MVP 全文改写**；明确永久不做项；路线图去 SaaS 化 |
| V2.5 | 2026-06-05 | App 拆分、缓存统一、移除部署残留 |
| V2.4 | 2026-06-05 | Phase 1.5：Token 成本、CI |
| ≤V2.3 | 2026-06-05 | 功能迭代与 UI 打磨（见 Git 历史） |
