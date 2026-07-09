# StockResearch 产品需求文档

**V10.3 · 开源 A 股市场研究 Agent**

> 唯一 PRD：`docs/PRD.md`（Git 中 `docs/` 仅推送本文件）。本地可选 `docs/meta.yaml` 供 prd-first 工具读取。

---

## 一、定位

本机联网运行的 **A 股 AI 研究 Agent**。不连券商、不代交易。

**北极星（Phase 1）**：单机体验完整 — 本地 Web UI + FastAPI + SQLite + BYOK。

帮助用户回答：**今天发生了什么 · 为什么与我有关 · 还需要验证什么**。

## 二、用户与双模式

| | 个人（advisor） | 专家（research） |
|--|----------------|-----------------|
| 语言 | 人话、金额、关联原因 | 术语直出、全量指标 |
| 术语弹窗 | 默认开 | 无 |
| 辩论 | 默认关 | 默认开 |
| 资产配置 | 按风险/现金流给参考 | 用户手动设目标，展示偏差 |

**契约**：同一推理管线产出同一 JSON/cards；仅渲染策略不同。禁止因模式改变事实层数值。

## 三、界面（Tri-Shell）

```text
┌─ 顶栏：指数 · 搜索 · 模式 · 告警铃 · 数据源 · 设置 ─────────────────────┐
├ lists-column ──┬─ center: [焦点][市场][风控][新闻] ┬─ copilot-column ──────┤
│ 持仓 · 自选    │ 多 Tab · K线 · ActionCenter      │ 多线程 · SSE · 免责    │
└────────────────┴─────────────────────────────────┴───────────────────────┘
```

- **四 Tab**：焦点 / 市场 / 风控 / 新闻
  - **市场 Tab**：A 股主要指数行情、指数分时、涨跌家数、北向资金；行业板块涨跌分布；指数与行业相关的主要新闻快讯
- **焦点多 Tab**：Sidebar 选中、Copilot 指令、顶栏指数各可占一 Tab
- **Copilot = 焦点 source of truth**：「分析茅台」→ 茅台 Tab；「茅台 vs 当前选中」→ 交叉对比
- **Demo 持仓**：空组合时 `/portfolio/demo` 快速体验
- 对话结束展示 **disclaimer**（与 API 字段同文）

## 四、核心能力

| 能力 | 说明 |
|------|------|
| 四维投研 | 基本面 / 技术面 / 情绪 / 筹码 → SSE 流式 |
| 多空辩论 | 可选；个人默认关、专家默认开 |
| 风控体检 | 规则引擎 + 可选 LLM 解读 |
| 新闻过滤 | 三层规则，3s SLA，零 LLM；统一 interest（持仓/自选/板块） |
| 价格告警 | APScheduler 5min；铃铛 + 可选浏览器 Notification |
| 定时简报 | 盘前 / 收盘；Cron 绑 uvicorn lifespan（Phase 1） |
| Action Center | 规则信号，零 LLM |
| 合规输出 | §六 语言政策 |

## 五、数据源

**原则**：分层降级、`partial` 显式标注缺口、禁止编造。不做 iFinD / Wind / Choice。

### 5.1 行情与 K 线

| 数据 | 主源 | 备源（按序） | 接口/说明 |
|------|------|--------------|-----------|
| 实时报价 | **新浪财经** `hq.sinajs.cn` | AkShare hist → **efinance** | 三源兜底 |
| 日 K 线 | **AkShare**（前复权 `stock_zh_a_hist`） | 新浪 K 线 → efinance | 指数用 `index_zh_a_hist` |
| 指数概览 | **新浪指数** | AkShare | 北向：AkShare `stock_hsgt_north_net_flow_in_em` |

### 5.2 新闻、公告、研报

| 数据 | 来源 | 说明 |
|------|------|------|
| 快讯 | **AkShare**（东方财富新闻） | 主路径 |
| 新闻兜底 | **博查 AI 搜索** | 需用户 `BOCHA_API_KEY`；AkShare 无结果时启用 |
| 上市公司公告 | **巨潮资讯** via AkShare | `stock_zh_a_disclosure_report_cninfo` |
| 机构研报 | **东方财富** via AkShare | `stock_research_report_em` |

### 5.3 财务与因子

| 数据 | 来源 | 说明 |
|------|------|------|
| 财务/估值 | AkShare | 默认 |
| 财务增强 | **Tushare Pro**（可选，用户 Token） | 有 Key 时优先；与 AkShare 冲突 → Tushare 为准 + UI 并列预警 |
| 筹码面 | AkShare | 龙虎榜、资金流、北向持股、两融、股东户数、解禁 |
| 情绪面 | AkShare + 东方财富个股新闻 + 雪球热度 | — |

### 5.4 冲突与降级

- **多源价差 >1%**：顶栏黄色预警；输出标注延迟/口径差异
- **`partial=true`**：可给方向性结论，须列出信息缺口
- **Tushare 未配置**：核心路径仍可用免费源

## 六、合规

| 禁止 | 加仓、减仓、持有观望（全界面） |
|------|-------------------------------|
| 默认允许 | 仓位偏高/偏低/适中；建议控制仓位；描述性风险 |
| 条件允许 | 建议买入/卖出 — 须同段附带 disclaimer |
| 禁止 | 目标价；确定性措辞；自动交易指令 |

## 七、推送与开关

| 开关 | 关 | 开 |
|------|----|----|
| 定时简报 | Cron 跳过，不写库 | 按 schedule 生成 |
| 价格告警 | Cron 跳过，不写库 | 5min 评估 |
| UI 轮询（默认关） | 不轮询 | 按间隔轮询；开启前展示延迟说明 |

推送阶段：P1 浏览器 Notification → P2 邮件（外挂 CLI）→ P3 短信 → 远期飞书。

Phase 2：`stockresearch worker` 独立 Cron + 可选 launchd 示例。

## 八、Phase 2 优先级

1. Settings 接 §七 开关；ingest 后台化；`stockresearch worker`
2. `prompts/` 外置
3. Tushare Registry 完善（可选）
4. CLI + MCP + Skills 外化（后期）

## 九、工程

```bash
uv run uvicorn stockresearch.api.app:app --reload --host 127.0.0.1 --port 8000 --app-dir src
cd web && npm run dev   # :5174
uv run pytest && cd web && npm run build
```

## 十、版本记录

| 版本 | 日期 | 说明 |
|------|------|------|
| **V10.3** | 2026-07-07 | 新增独立「市场」Tab；prompts 外置；定时任务独立 worker CLI |
| V10.2 | 2026-07-01 | 精简 PRD；数据源按代码现状重写（新浪/AkShare/efinance 三层行情；K 线 AkShare 优先） |
| V10.1 | 2026-06-30 | 双模式契约；合规语言；Focus 多 Tab；§7 开关语义 |
| V10.0 | 2026-06-29 | 唯一 PRD；三 Tab tri-shell；统一 chat 路由 |
