# StockResearch 产品需求文档

**V10.8 · 开源 A 股市场研究 Agent**

> 唯一 PRD：`docs/PRD.md`。Git 中 `docs/` 还推送 `screenshots/` 界面预览图。本地可选 `docs/meta.yaml` 供 prd-first 工具读取。

---

## 一、定位

本机联网运行的 **A 股 AI 研究 Agent**。不连券商、不代交易。非机构终端（不做 Wind / iFinD / Choice）。

**北极星（Phase 1）**：单机体验完整 — 本地 Web UI + FastAPI + SQLite + BYOK。

**北极星演进（Phase 3+）**：在完整单机体验之上，强调 **证据是否充分 · 结论能否被事后验证**。

帮助用户回答：**今天发生了什么 · 为什么与我有关 · 还需要验证什么**。

深度投研交付「可核对证据」；轻量化交付「可验证假设/信号」——因子与回测服务于验证研究结论，不是第二套量化产品。

## 二、用户与双模式

| | 个人（advisor） | 专家（research） |
|--|----------------|-----------------|
| 语言 | 人话、金额、关联原因 | 术语直出、全量指标 |
| 术语弹窗 | 默认开 | 无 |
| 辩论 | 默认关 | 默认开 |
| 资产配置 | 按风险/现金流给参考（API `/advisor/allocation` 已就绪） | 用户手动设目标，展示偏差（Phase 4 后续；当前未实现，UI 面板 `AssetAllocationPanel` 已就 advisor 模式实现但暂未挂载主流程） |
| 证据链 | 默认折叠 | 默认展开 |

**契约**：同一推理管线产出同一 JSON/cards；仅渲染策略不同。禁止因模式改变事实层数值。

**表达档（reading_mode，与双模式正交的渲染策略）**：`friendly`（人话、金额感受、类比）对应 advisor 默认；`professional`（术语直出、全量指标）对应 research 默认；`standard`（中文术语 + 首次出现半句白话）为可选中间档，由用户在设置中显式选择。三档仅控制 LLM 文本措辞与术语呈现密度，不改变 score / confidence / 估值分位等事实层数值；`enable_glossary` 独立控制术语弹窗标记，与 reading_mode 解耦。

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
- 深度研究落在 Copilot 报告卡（证据链）；焦点区可附财务摘要条，不新开整页工作簿

## 四、核心能力

| 能力 | 说明 |
|------|------|
| 四维投研 | 基本面 / 技术面 / 情绪 / 筹码 → SSE 流式；基本面含公告/研报证据 |
| 证据链 | highlights/risks 可挂 source、date、snippet；显式信息缺口（`partial`） |
| 多空辩论 | 可选；个人默认关、专家默认开 |
| 大师点评 | 可选；用户勾选 1–N 位（巴菲特 / 芒格 / 伯里，可扩展自定义）→ 在四维研报与风控报告条件性挂载独立 commentary；受 `enable_master_commentary` 与 `enable_llm_analysis` 双重开关控制，默认关；不替代主结论，仅作辅助视角 |
| 风控体检 | 规则引擎 + 可选 LLM 解读（`enable_llm_analysis` 开关，默认开；关时仅规则+量化指标） |
| 新闻过滤 | 三层规则，3s SLA，零 LLM；统一 interest（持仓/自选/板块） |
| 价格告警 | APScheduler 5min；铃铛 + 可选浏览器 Notification |
| 定时简报 | 盘前 09:05 / 盘中 11:35 / 盘后 15:35；Cron 在独立 worker 运行 |
| Action Center | 规则信号，零 LLM |
| 研究信号验证 | 历史研报 bias / 因子阈值 → 前向收益统计；单报告事后核对；仅前复权日线（研究验证，非策略回测器） |
| 数值因子 | 估值分位、动量、波动等可计算因子；证据覆盖清单与因子分离；报告附日线口径戳记 |
| 纸上持仓假设 | 风控定量压力情景 + 最大行业/个股相对现价冲击（非历史回放） |
| 合规输出 | §六 语言政策 |

**明确非范围**：三表完整会计引擎 / DCF 产品化；vectorbt 级策略回测、滑点撮合、组合优化、模拟盘账户；实盘信号下单；为量化单独做第三套 UI Shell。验证与纸上冲击仅服务于「结论可核对 / 仓位假设可感知」。

## 五、数据源

**原则**：分层降级、`partial` 显式标注缺口、禁止编造。不做 iFinD / Wind / Choice。

### 5.1 行情与 K 线

| 数据 | 主源 | 备源（按序） | 接口/说明 |
|------|------|--------------|-----------|
| 实时报价 | **新浪财经** `hq.sinajs.cn` | AkShare hist → **efinance** | 三源兜底 |
| 日 K 线 | **AkShare**（前复权 `stock_zh_a_hist`） | efinance → **Tushare**（有 Token）→ 新浪（非 qfq） | 指数用 `index_zh_a_hist`；本地日线仓增量缓存持仓/自选/近期研报标的 |
| 指数概览 | **新浪指数** | AkShare | 北向：AkShare `stock_hsgt_north_net_flow_in_em` |

### 5.2 新闻、公告、研报

| 数据 | 来源 | 说明 |
|------|------|------|
| 快讯 | **东财 + 财联社/同花顺/新浪**（AkShare 多源 flash） | 本地优先，标题去重时 CLS 优先 |
| 新闻兜底 | **博查 AI web-search** + URL 短摘录 fetch | 需用户 Key；本地偏空时符号感知 query；失败不拖垮 |
| 上市公司公告 | **巨潮资讯** via AkShare | 接入四维基本面主链路 |
| 机构研报 | **东方财富** via AkShare | 接入四维基本面主链路 |

### 5.3 财务与因子

| 数据 | 来源 | 说明 |
|------|------|------|
| 财务/估值 | AkShare | 多期序列 + 真实估值分位；缺则 `partial` |
| 财务增强 | **Tushare Pro**（可选 L3，用户 Token） | 有 Token 时进估值（东财后）与 qfq 日线兜底；Registry=元数据+状态探针+降级链，非行情 conflict ledger |
| 筹码面 | AkShare | 龙虎榜、资金流、北向持股、两融、股东户数、解禁 |
| 情绪面 | AkShare + 东方财富个股新闻 + 雪球热度 | — |
| 数值因子 | 本地日线仓 + 财务/筹码快照 | `momentum`/`volatility`/`pe_percentile` + 主力净流入/北向持股；写入 `factors` |

### 5.4 冲突与降级

- **多源价差 >1%**：顶栏黄色预警；输出标注延迟/口径差异
- **`partial=true`**：可给方向性结论，须列出信息缺口
- **Tushare 未配置**：核心路径仍可用免费源
- **估值分位不可算**：禁止静默填 `0.5`；须 `partial` + 缺口说明

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

**调度器跨进程互斥**：API（`RUN_SCHEDULERS_IN_API=true`）与 worker 不会同时运行同一调度器。启动时通过文件锁（`scheduler.lock`，置于 SQLite 数据库同目录）实现跨进程互斥；后启动的一方检测到锁被占用即跳过调度器启动（API 仅跳过调度器但仍正常服务请求，worker 直接退出码 1）。内存数据库（`sqlite://`）跳过锁。

## 八、路线图优先级

### Phase 2（基础设施）

1. ~~Settings 接 §七 开关；ingest 后台化；`stockresearch worker`~~（已完成）
2. ~~`prompts/` 外置~~（已完成）
3. ~~Tushare Registry（元数据+状态探针+估值/qfq 降级）~~（MVP 已完成）
4. CLI + MCP + Skills 外化（后期）
5. 可选 launchd 示例（worker 常驻）

### Phase 3（证据加深）

1. 公告/研报接入四维基本面主链路
2. 财务多期序列、真实估值分位、动态可比
3. 报告 evidence schema + Copilot 证据/缺口/因子条；缺口可追问

### Phase 4（轻量化）

1. SQLite 日线仓 + worker 增量拉取持仓/自选宇宙（因子/验证强制 qfq）
2. 可计算数值因子（与证据覆盖清单分离）
3. 研究信号验证升级（文案称「验证」，非策略回测；偏向/因子分列；单报告事后核对）
4. 纸上持仓假设（风控相对现价冲击，非模拟盘）

## 九、工程

```bash
uv run uvicorn stockresearch.api.app:app --reload --host 127.0.0.1 --port 8000 --app-dir src
cd web && npm run dev   # :5174
uv run pytest && cd web && npm run build
```

## 十、版本记录

| 版本 | 日期 | 说明 |
|------|------|------|
| **V10.8** | 2026-07-16 | §七 补登记调度器跨进程互斥机制（文件锁）；§5.1 K 线默认 AkShare 优先对齐代码现状 |
| **V10.7** | 2026-07-14 | §四 补登记「大师点评」为正式特性；风控 `enable_llm_analysis` 可选开关语义写明 |
| **V10.6** | 2026-07-13 | 投研/投顾可靠性：qfq 日线仓、证据因子条、验证分列与事后核对、纸上冲击假设 |
| V10.5 | 2026-07-13 | README 纳入最新 UI 截图（`docs/screenshots/`） |
| V10.4 | 2026-07-11 | 方向：深度证据 + 轻量可验证；Phase 3/4 路线图；公告研报进主链路；数值因子与研究验证语义 |
| V10.3 | 2026-07-07 | 新增独立「市场」Tab；prompts 外置；定时任务独立 worker CLI；新闻 ingest 后台 job；盘前/盘中/盘后三段简报 |
| V10.2 | 2026-07-01 | 精简 PRD；数据源按代码现状重写（新浪/AkShare/efinance 三层行情；K 线 AkShare 优先） |
| V10.1 | 2026-06-30 | 双模式契约；合规语言；Focus 多 Tab；§7 开关语义 |
| V10.0 | 2026-06-29 | 唯一 PRD；三 Tab tri-shell；统一 chat 路由 |
