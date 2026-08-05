# StockResearch <img src="../desktop/branding/app-icon.png" alt="StockResearch logo" width="32" height="32" align="middle"> 产品需求文档

**V10.17 · 开源 A 股市场研究 Agent**

> 唯一 PRD：`docs/PRD.md`。Git 中 `docs/` 还推送 `screenshots/` 界面预览图。本地可选 `docs/meta.yaml` 供 prd-first 工具读取。

---

## 一、定位

本机联网运行的 **A 股 AI 研究 Agent**。不连券商、不代交易。非机构终端（不做 Wind / iFinD / Choice）。

**产品对标 Google Finance**：免费的个人投资者行情与组合跟踪产品形态。在同等免费数据约束下，用 AI 编排把专业投研能力平民化——让没有金融基础的用户也能获得专业级投研体验。

**北极星（Phase 1）**：单机体验完整 — 本地 Web UI + FastAPI + SQLite + BYOK。

**北极星演进（Phase 3+）**：在完整单机体验之上，强调 **证据是否充分 · 结论能否被事后验证**。

帮助用户回答：**今天发生了什么 · 为什么与我有关 · 还需要验证什么**。

**深度分析演进（Phase 10）**：在四维证据之上，用可核对因果链回答 **为何涨跌 · 现价定了什么 · 主张如何证伪**（Impact → Pricing → Thesis）。因子与验证服务于该链条，不是第二套量化产品。

深度投研交付「可核对证据」；轻量化交付「可验证假设/信号」。

## 二、用户与双模式

| | 个人（advisor） | 专家（research） |
|--|----------------|-----------------|
| 语言 | 人话、金额、关联原因 | 术语直出、全量指标 |
| 术语弹窗 | 默认开 | 无 |
| 资产配置 | 按风险/现金流给参考（`/advisor/allocation`；风控 Tab 挂载 `AssetAllocationPanel`） | 用户自设板块目标权重 vs 持仓偏差（`/portfolio/allocation/deviation` + `AllocationDeviationPanel`；只展示，不做再平衡） |
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
  - **市场 Tab**：A 股主要指数行情、指数分时、涨跌家数、北向资金；行业板块涨跌分布；指数与行业相关的主要新闻快讯；大盘深研含宏观指标与外围市场上下文，涨跌归因讲纪律（原因须有证据）
- **焦点多 Tab**：Sidebar 选中、Copilot 指令、顶栏指数各可占一 Tab
- **Copilot = 焦点 source of truth**：「分析茅台」→ 茅台 Tab；「茅台 vs 当前选中」→ 交叉对比
- **Copilot 对话线**：仅点「+」开新线程；未点「+」时同窗口续问落在当前线程，共用同一 `session_id`，回合写入会话记忆（`conversations.messages`）
- **意图路由**：规则 + LLM 兜底的五类意图分类（个股 / 市场 / 行业 / 新闻 / 通用）；按意图装配 `ChatContextScope`（持仓/自选/页面上下文），新闻与工具按 scope 过滤；仅 UI 页面上下文不触发次要域
- **Demo 持仓**：空组合时 `/portfolio/demo` 快速体验
- 对话结束展示 **disclaimer**（与 API 字段同文）
- 深度研究落在 Copilot 报告卡（证据链）；焦点区可附财务摘要条，不新开整页工作簿

## 四、核心能力

| 能力 | 说明 |
|------|------|
| 四维投研 | 基本面 / 技术面 / 情绪 / 筹码 → SSE 流式；基本面含财务/公告/研报；情绪含个股新闻；**新闻与财报是四维内证据，不是平行产品** |
| 分析深度档 | 显式预算档 `standard` / `comprehensive` / `deep`（文案：标准 / 综合 / 深度）；只调节四维内工具与证据预算，不另开管线 |
| 证据链 | highlights/risks 可挂 source、date、snippet；显式信息缺口（`partial`） |
| 风控体检 | 规则引擎 + 可选 LLM 解读（`enable_llm_analysis` 开关，默认开；关时仅规则+量化指标） |
| 新闻过滤 | 三层规则，3s SLA，零 LLM；统一 interest（持仓/自选/板块） |
| 价格告警 | APScheduler 5min；铃铛 + 可选浏览器 Notification |
| 定时简报 | 盘前 09:05 / 盘中 11:35 / 盘后 15:35；Cron 在独立 worker 运行；盘前/盘后含行业板块涨跌榜块与持仓所属行业标注，盘后复盘对照当日盘前观点 |
| Action Center | 规则信号，零 LLM |
| 研究信号验证 | 历史研报 bias / 因子阈值 → 前向收益统计；单报告事后核对；仅前复权日线（研究验证，非策略回测器）；深度档可露出入口，不静默自动跑 |
| 研究复盘时间线 | 同标的多份研报时间线：结论/因子快照变化 + 可挂事后核对（Phase 7a） |
| 桌面壳 | Tauri 2（macOS/Windows）：拉起本机 uvicorn + 可选 worker，窗口打开托管 UI（Phase 8） |
| 数值因子 | 估值分位、动量、波动等可计算因子；证据覆盖清单与因子分离；报告附日线口径戳记；综合及以上默认展开因子条并附「与结论是否同向」一句 |
| 纸上持仓假设 | 风控定量压力情景 + 最大行业/个股相对现价冲击（非历史回放） |
| 合规输出 | §六 语言政策 |
| 意图路由上下文 | 规则 + LLM 兜底五类意图分类；按意图装配 ChatContextScope；新闻与工具按 scope 过滤；仅页面上下文不触发次要域 |
| LLM 错误透传 | 聊天回复透出具体 LLM 错误详情（Key / 配额 / 网络），便于 BYOK 排障 |

### 4.1 分析深度档（四维预算）

**定位**：综合 / 深度 = 四维投研的证据与工具预算，不是「新闻分析 / 财报分析」独立产品，也不是第二套量化产品。

| 档位 | key | 含义 |
|------|-----|------|
| 标准 | `standard` | 现况四维基线 |
| 综合 | `comprehensive` | 标准 + 新闻/财报证据加厚 + 因子条默认展开 |
| 深度 | `deep` | 综合 + 更高证据预算；可挂信号验证入口 |

**UI 契约**：
- 设置项 `analysis_depth`（与 mode settings 同通道持久化）
- 建议默认：advisor → `standard`，research → `comprehensive`（事实层数值仍不因模式改写）
- 单次覆盖：Copilot 话术 / `skill_stock_research.args.analysis_depth` / 研究 API query 参数；只影响本轮，不改设置
- 优先级：`Skill/API args > 本轮已解析话术 > settings.analysis_depth > standard`
- 轻量工具路径（报价/单条新闻等）**不升档**；仅进入个股四维 Skill 或研究 API 时应用预算
- 新闻 Tab 单篇深析保持旁路；深度档可将 1～2 条关键新闻交叉核对**回注情绪维**，不改新闻 Tab 主路径

**档位预算（相对 standard 基线）**：

| 维度 | standard | comprehensive | deep |
|------|----------|---------------|------|
| 基本面·财务 | 财务/估值/比率快照 | + 多期 YoY/QoQ 要点（缺则 `partial`） | + 更长窗口（约 8～12 期）与同比结构一句 |
| 基本面·公告 | 近 60 天、最多约 8 条 | 业绩/预告/快报优先；摘录加长进 evidence | 再扩条数（约 12）+ 减持/回购/问询等进风险 |
| 基本面·研报 | 最多约 6 条 | 强制进 highlights/risks 引用 | 评级等仅作机构观点证据（不自造目标价） |
| 情绪·新闻 | 标题 + 标题分 + text_factor | + 事件聚类进情绪维 | + 1～2 条关键新闻交叉核对回注情绪维 |
| 技术 / 筹码 | 现状 | 维持；综合结论引用 score | 维持；与其它维矛盾时须显式写出 |
| 数值因子 | 现有 5 因子，可折叠 | 默认展开 + 与结论同向一句；起算质量/成长因子 | 同左必算；露出信号验证入口（点选/指令） |

实现上收敛为内部只读 `AnalysisBudget`（公告窗口/条数/摘录长度、财务期数、新闻聚类与交叉核对次数、因子 key 列表等）；各维工具与因子计算读 budget，禁止散落 magic number。报告元数据回传 `analysis_depth`。

**明确非范围**：三表完整会计引擎 / DCF 产品化；vectorbt 级策略回测、滑点撮合、组合优化、模拟盘账户；实盘信号下单；为量化单独做第三套 UI Shell；独立「财报 Tab」或与四维平行的新闻/财报分析产品。验证与纸上冲击仅服务于「结论可核对 / 仓位假设可感知」。

## 五、数据源

**原则**：分层降级、`partial` 显式标注缺口、禁止编造。不做 iFinD / Wind / Choice。

### 5.1 行情与 K 线

| 数据 | 主源 | 备源（按序） | 接口/说明 |
|------|------|--------------|-----------|
| 实时报价 | **新浪财经** `hq.sinajs.cn` | AkShare hist → **efinance** | 三源兜底 |
| 日 K 线 | **AkShare**（前复权 `stock_zh_a_hist`） | efinance → **Tushare**（有 Token）→ 新浪（非 qfq） | 指数用 `index_zh_a_hist`；本地日线仓增量缓存持仓/自选/近期研报标的 |
| 指数概览 | **新浪指数** | AkShare | 北向：AkShare `stock_hsgt_north_net_flow_in_em` |
| K 线画线层 | 9a 前端自动趋势线 + 9b 后端算法（`GET /market/overlays`） | 水平参考线未做 | 前后端同 `ChartOverlaySet` schema（source `"algo"`/`"ai"`）；摆动点拟合支撑/压力虚线，距现价 ≤15% 过滤，≤4 条，默认开；Copilot 画线卡片可一键上屏；非交易信号；另有滚轮缩放归一化 |

**画线层契约（`ChartOverlaySet`）**：见 §八 Phase 9。Phase 9a 纯前端；9b 同一 JSON 供 Copilot 筛选/解说。

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
| 数值因子 | 本地日线仓 + 财务/筹码快照 | 基线：`momentum_20d` / `volatility_20d` / `pe_percentile` / `main_net_inflow_5d` / `northbound_hold_pct`；综合起算、深度必算质量/成长类（`roe_ttm`、`revenue_yoy`、`np_yoy`、`pb_percentile`）及相对同业（`peer_rel_momentum_20d`、`peer_rel_pe_percentile`）；PE/PB 历史分位有序列才算，缺则 `partial`，禁止填默认分位；写入 `factors` |

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

### Phase 2（基础设施）✅ 基本完成

1. ~~Settings 接 §七 开关；ingest 后台化；`stockresearch worker`~~（已完成）
2. ~~`prompts/` 外置~~（已完成）
3. ~~Tushare Registry（元数据+状态探针+估值/qfq 降级）~~（MVP 已完成）
4. CLI 已落地（`cli/research_tools.py`：timeline/hypothesis/compare/export，JSON 输出）；**MCP + Skills 外带未做**
5. 可选 launchd 示例（worker 常驻）——未做

### Phase 3（证据加深）✅

1. 公告/研报接入四维基本面主链路
2. 财务多期序列、真实估值分位、动态可比
3. 报告 evidence schema + Copilot 证据/缺口/因子条；缺口可追问

### Phase 4（轻量化）✅（日线仓/因子/信号验证/纸上冲击均已落地）

1. SQLite 日线仓 + worker 增量拉取持仓/自选宇宙（因子/验证强制 qfq）
2. 可计算数值因子（与证据覆盖清单分离）
3. 研究信号验证升级（文案称「验证」，非策略回测；偏向/因子分列；单报告事后核对）
4. 纸上持仓假设（风控相对现价冲击，非模拟盘）

### Phase 5（四维深预算）✅（`analysis_depth` 三档 + 预算注入已落地）

在仍走单一四维管线的前提下，落地 §4.1：

1. **P0 档位骨架**：`analysis_depth` 设置 + Skill/API/话术覆盖 + `AnalysisBudget` + 报告元数据；单测覆盖优先级
2. **P1 财报加厚**：comprehensive/deep 多期 YoY/QoQ、业绩公告优先与摘录；deep 扩条数与风险类公告
3. **P2 新闻加厚**：comprehensive 情绪维事件聚类；deep 1～2 条关键新闻交叉核对回注情绪维（新闻 Tab 旁路不变）
4. **P3 因子与验证**：质量/成长因子；因子条默认展开与同向句；deep 信号验证入口（非静默）

**产品验收**：设置选综合且无覆盖 → 报告 `analysis_depth=comprehensive` 且因子条展开；「深度分析{标的}」本轮为 deep、设置不变；deep 证据密于 standard，缺数 `partial`；轻问报价不升档。

### Phase 6（可带走的研究验证）✅ 完成（导出/PIT/compare/event-study/hypothesis/批量四维与前端批量入口均已落地）

仍不做策略回测器 / 第三套量化 Shell。API/能力清单如下；**产品叙事与主界面拼装以 Phase 10 三层为准**（事件研究并入 Impact，假设验证/时间线并入 Thesis，导出与 PIT 为横切）。

1. **机器可读导出**：报告 JSON（`stockresearch.report.v1`）+ CSV 因子表；Markdown/PDF 附日线口径与数值因子
2. **点-in-time 声明**：事后核对 / 信号验证显式 `point_in_time` + `signal_as_of`；只用报告快照因子 + 之后的 qfq 日线，不重拉事后财务
3. **自选对比与批量**：`POST /research/compare` 因子并排；`POST /research/batch` 批量四维（≤8）——**工具能力，不进 DeepAnalysisBlock 核心叙事**
4. **事件研究**：`GET /research/event-study` 以公告日为 t0 的前向收益（业绩/风险过滤）——Impact 层数据核
5. **假设一键验证**：`POST /research/hypothesis/verify` 预设规则，历史条件触发后量收益——Thesis 层压测面

### Phase 7（研究 OS 加厚 · 仍非交易）🚧 大部分完成

不做真实交易场景（滑点/撮合/组合优化/再平衡引擎/模拟盘/实盘）。**7a 并入 Phase 10 落地波次**；7b/7c 仍按序在 10 之后或并行外缘。状态：7a ✅（timeline + 事后核对）；7b ✅（自选雷达已接 Action Center；缺口一键补跑 `POST /research/refill` + 研报卡按钮已落地）；7c ✅ 大部分（配置偏差 ✅、CLI ✅；MCP 未做）。

#### 7a · 核（验证与复盘）→ 见 Phase 10 L2/L3

1. **研究复盘时间线**：同标的历史研报按时间排列；展示 bias / 分数 / 关键因子（及 Thesis）快照变化；可挂载各报告事后核对（点-in-time）。API：`GET /research/timeline`。
2. **验证规则加厚**：假设验证预设扩展（估值×动量、ROE/成长相关等研究型规则，仍非策略）；服务 Thesis 压测，不另开「回测产品」。
3. **因子可信度**：`pb_percentile` 尽量给真实历史分位（不能则明确 `partial`）；PE/PB 缺口更显眼；与 Pricing 层**同一数值源**（禁止两套 PE）。

#### 7b · 日常（闭环与雷达）

4. **证据缺口闭环**：报告 `data_gaps` / partial 因子可在 Copilot 一键「只补缺口再跑」或定向补拉公告/财务，不新开平行产品 Tab。
5. **自选研究雷达**：零 LLM 规则信号（因子与上次结论背离、临近财报窗口、事件研究样本变差等）→ Action Center / 简报；非交易信号文案。

#### 7c · 外缘（感知与外带）

6. **专家模式资产配置偏差**：用户自设目标权重 vs 当前持仓偏差展示（挂主流程）；**不做**优化器与再平衡建议引擎。
7. **CLI / MCP 外带**：`stockresearch research {timeline,hypothesis,compare,export}` 输出 JSON（便于 Jupyter/管道）；与 HTTP 研究验证 API 同源。完整 MCP server 可后续薄包同一套函数，不另开产品面。

**产品验收（分波）**：7a 同标的 ≥2 份报告可见时间线且可挂事后收益；假设预设 > 动量四条；因子缺数不填默认分位。7b 缺口可追问补跑；自选雷达有 ≥1 条规则进 Action Center。7c research 模式可见配置偏差；CLI/MCP 至少覆盖 export + timeline + hypothesis。

### Phase 8（桌面壳 · macOS / Windows）✅（Tauri 2 已可用，见 `desktop/`）

用 **Tauri 2** 包本机壳，不重做业务 UI：窗口加载已由 FastAPI 托管的 `web/dist`（`http://127.0.0.1:8000`）。

1. **双端壳**：`desktop/` Tauri 工程；目标平台 macOS + Windows
2. **进程编排**：启动时拉起 `uv run uvicorn … --app-dir src`；可选拉起 `stockresearch worker`（默认关，`STOCKRESEARCH_DESKTOP_WORKER=1` 开启）；退出时回收子进程
3. **就绪门闩**：轮询 `/health` 后再显示主窗；若端口已有健康服务则复用、不重复拉起
4. **工程约定**：打包不捆绑 Python 运行时（MVP）；要求本机已 `uv sync` + `web` 已 `npm run build`；可用 `STOCKRESEARCH_ROOT` 指向仓库根
5. **非目标**：移动端 App；把 AkShare/模型打进安装包；Electron

**产品验收**：macOS / Windows 上 `npm run tauri dev`（或等价）能打开窗口并完成登录/持仓/对话一条主路径；退出后 8000 端口无残留本壳拉起的 uvicorn（复用外部已有服务时不杀）。

### Phase 9（K 线算法画线 · 再接 Copilot）🚧 9a 部分落地 / 9b ✅ 已落地

在现有 `lightweight-charts`（`MarketChart`：K 线 + MA + 量 + MACD/RSI）上叠加**算法画线层**；手动画线 / 斐波那契 / 通道 / 用户线持久化 **不做**。合规：线旁与 Copilot 解说均禁止买卖建议措辞。

#### 9a · 前端自动层（先行落地）🚧 部分实现

**V10.16 实现状态**：自动趋势线已落地（`web/src/chartTrendlines.ts`，见上文 §5.1）；滚轮/触控板缩放归一化已修复。以下规格保留为后续目标（水平参考线、createPriceLine、`ChartOverlaySet` 前后端共用 schema、可视区间重算防抖）。

1. **开关**：`StockChart` 工具栏「画线」toggle，默认 **开**；与 MACD/RSI 并列。
2. **算法模块**：`web/src/chartOverlays.ts`（与 `chartIndicators.ts` 并列），输入已加载 `KlineBar[]` + 可见逻辑区间。
3. **趋势线**：仅用**当前可见** bars；摆动高/低（默认左右各 **3** 根）→ 同侧有效点连线 → 按未破/触碰打 `strength`；最多约 1 上 + 1 下（计入总上限）。可见 bars 少于 **20** 则跳过趋势线。
4. **水平参考线**：用已加载历史，上限 **180** 根；摆动价聚类（容差优先 **ATR(14)×0.5**，ATR 不可用时用价的 **0.8%**）→ 触碰计分；最多约 2 条。
5. **截断**：合并后按 `strength` 排序，默认展示 **≤ 4** 条。可见区变化约 **150ms** debounce 重算趋势线；bars 集合变化时重算水平线。bars 过少则静默不画。
6. **渲染**：趋势用 `addLineSeries`；水平用 `createPriceLine`。支撑/压力分色；无交易文案。

**数据模型（前后端共用 shape，9a 仅前端产出）**：

```ts
type ChartOverlay =
  | {
      id: string;
      kind: "trend";
      a: { time: string; price: number };
      b: { time: string; price: number };
      side: "support" | "resistance";
      strength: number; // 0–1
      source: "algo";
    }
  | {
      id: string;
      kind: "level";
      price: number;
      strength: number;
      touches: number;
      source: "algo";
    };

type ChartOverlaySet = {
  symbol: string;
  generatedAt: string;
  overlays: ChartOverlay[];
};
```

**测试**：摆动点 / 聚类 / 排序截断单测（固定 fixtures）；toggle 开关键线出现与清除。

#### 9b · Copilot 复用 ✅ 已落地（V10.17）

1. `ChartOverlaySet`/`ChartOverlay` 抽到后端 Pydantic schema（`core/schemas.py`）；`services/chart_overlays.py` Python 移植前端 `chartTrendlines.ts` 算法（左右各 3 根摆动点、≤4 条、距现价过滤），`GET /market/overlays?symbol=` 输出。
2. Copilot「画趋势线 / 支撑位在哪」→ `skill_chart_overlays` 返回 overlay 卡片 + 模板化描述性解读（禁交易措辞）；`source="ai"`，附 `rationale`。
3. 对话卡片一键「在图表显示」，经 9a 同一 `addLineSeries` 渲染路径上屏（SparseDotted 虚线，标注 AI）。

**产品验收（9a）**：个股 K 线默认可见 ≤4 条算法线；关「画线」后全部消失；滚动可见区时趋势线更新、水平线不乱跳；无买卖措辞。**9b**：对话可触发画线并附描述，schema 与 9a 一致。

### Phase 10（深度分析三层 · Impact / Pricing / Thesis）✅ W1–W3 已落地

`deep_analysis`（impact / pricing_bridge / thesis_build）已接入 `ResearchReportOut` 与综合/深度档；以下为原规划记录：

将 Phase 6–7a 能力与「归因 / 定价桥 / 可证伪主张」**去重合并**为一条深度分析主线。不新开平行产品 Tab；不引入 Qlib；不做完整 DCF；不做策略回测 Shell / 实盘。

**深度定义**：因果链完整且可核对——已实现涨跌（Impact）→ 现价含义（Pricing）→ 前瞻路径与证伪（Thesis）。每层有确定性计算内核；LLM 只解释与串联，**禁止另造与计算层冲突的数字**。

#### 10.0 架构（唯一骨架）

| 层 | 回答 | 合并自 | 主产出 |
|----|------|--------|--------|
| **L1 Impact** | 为何涨跌 | 归因 + 6.4 事件研究 | 市场/行业/特异分解 + 事件冲击 |
| **L2 Pricing** | 现价定了什么 | 定价桥 + 7a.3 因子可信 + 现有因子条 | 盈利×倍数分解；可选隐含增速；因子内嵌 |
| **L3 Thesis** | 走向靠什么、错了怎么认 | Thesis + 6.5/7a.2 假设验证 + 7a.1 时间线 | 主张 / 监控 / 失效；验证与复盘为其两面 |
| **横切 Accuracy** | — | 6.1 导出 + 6.2 PIT | 全层强制；不当独立「深度卖点」 |

**deep 报告块顺序**（`analysis_depth=deep` 必出 L1–L3；`comprehensive` 可出简化 L1，L2/L3 可选）：

1. 四维证据（现有，不扩平行维）
2. Impact
3. Pricing（因子数字只在此呈现一次，不另开因子秀）
4. Thesis（旁路「验证这条」与「历史结论/时间线」）
5. 导出含 `deep_analysis` + PIT 戳记

Copilot：深度档默认先答「为何动」，再答观点与主张。

#### 10.1 L1 Impact（W1）

**计算**

- 窗口默认近 **20** 个交易日（可配置，须写入报告元数据）。
- 个股超额近似：对市场指数与行业指数做收益分解，得到 **市场贡献 / 行业贡献 / 特异收益**（单因子或两步残差即可；模型名与 R² 写入 payload）。
- 特异收益绝对值最高的交易日（默认 top **3**）尝试挂载同期公告/事件；有则附事件研究窗收益摘要，无则显式 `unexplained`（流动性/情绪等，禁止编造原因）。
- 复用/延伸 `GET /research/event-study`；主界面与报告共用同一计算结果。

**准确性**

- 仅前复权日线；估计窗与事件窗分离（防前视）。
- 缺行业指数或样本不足 → `partial=true` + 缺口说明，**禁止硬凑 β**。

**验收**：焦点股 deep 报告可见三分解；至少一处特异高峰有事件挂载或明确 `unexplained`；导出含 `deep_analysis.impact`。

#### 10.2 L2 Pricing（W2）

**计算**

- 在可得财务/估值序列上分解近期涨跌中的 **盈利变化贡献 vs 倍数变化贡献**（窗口与口径戳记必写）。
- 可选：在简化假设下给出 **隐含增速**（反向推演）；数据不足则整段 `partial`，不输出假精确。
- **不做**完整三表会计引擎 / 产品化 DCF / 自造目标价。
- PE/PB 分位、质量/成长因子与 Pricing **同源**；报告内禁止出现两套不一致的 PE。

**准确性**

- 无历史序列则不分位、不填默认 0.5。
- 口径（TTM/LYR、前复权）与因子条、导出一致。

**验收**：deep 报告有定价桥或明确 partial；因子数值与 Pricing 引用一致；无目标价。

#### 10.3 L3 Thesis（W3）

**结构**（报告必出块，非可选散文）

```ts
type Thesis = {
  claim: string;           // 核心主张（描述性，非下单指令）
  evidence_ids: string[];  // 指向四维/Impact/Pricing 证据
  monitors: string[];      // 关键跟踪变量
  invalidate_if: string[]; // 失效条件
  horizon: string;         // 时间窗表述
  scenarios?: { base: string; upside?: string; downside?: string };
};
```

**验证与复盘（Thesis 的两面，不另开产品）**

- `hypothesis/verify` 规则加厚（估值×动量、ROE/成长等），用于压测主张相关假设；文案称「研究验证」。
- `timeline` 展示同标的历史结论 / Thesis 变更，可挂事后收益（PIT）。

**准确性**

- 验证与事后核对：`point_in_time=true`，只用报告快照因子 + 之后 qfq 日线，不重拉事后财务。
- 禁止伪装精确目标价与买卖指令（§六）。

**验收**：deep 报告必有 Thesis 四要素（claim / evidence_ids / monitors / invalidate_if）；至少一条研究型假设规则可跑；同标的 ≥2 份报告时时间线可见且可挂事后收益。

#### 10.4 横切与非目标

- **导出**：`stockresearch.report.v1` 增加 `deep_analysis: { impact, pricing, thesis }`；MD/PDF 同步摘要。
- **PIT**：Impact 事件窗、Thesis 验证、时间线事后核对共用纪律。
- **非目标**：Qlib 依赖；vectorbt 级策略回测 UI；完整 DCF；BUY/SELL 北极星；为深度分析新开第四套 Shell；compare/batch 塞进主叙事。

#### 10.5 落地波次

| 波次 | 交付 | 对应 |
|------|------|------|
| **W1** | Impact 进焦点/Copilot/报告 + 事件挂载 + 导出字段 + PIT | L1 · 6.2 · 6.4 · 部分 6.1 |
| **W2** | Pricing 桥 + 因子可信/同源收束 | L2 · 7a.3 |
| **W3** | Thesis schema + 假设规则加厚 + 时间线复盘 Thesis | L3 · 6.5 · 7a.1 · 7a.2 |

**产品验收（Phase 10）**：`analysis_depth=deep` 时报告块顺序为四维→Impact→Pricing→Thesis；三层缺数均 `partial` 而非静默编造；导出含 `deep_analysis` 与 PIT 戳记；无交易指令与自造目标价。

**实现计划（本机）**：`docs/superpowers/plans/2026-08-01-phase10-deep-analysis.md`（`docs/*` 除 PRD/screenshots 外不入库；供 Agent 按任务执行 W1→W3）。

### Phase 11（普通用户化 · Plain-Language）🚧 进行中

**定位**：面向无金融基础的普通用户（免费数据、AI 增强投顾）。原则：不新增“看起来专业但不实用”的功能；帮用户更快理解「这是什么 / 为什么重要 / 对我有什么影响 / 有什么风险 / 下一步可以做什么」。

#### 11.0 表达档位（两档）

`reading_mode` 由三档收敛为**两档**：`friendly`（普通版，默认）与 `professional`（专业版）；存量 `standard` 值一律归一为 `friendly`。普通版规范见 `prompts/advisor_plain_language.md`（升级版）：平实克制、术语首现必解释、数字翻译成影响、风险/不确定性/免责必保留、建议以选项形式给出不下指令、禁用未解释术语连排（估值分位/动量/风险敞口/夏普比率/回撤/边际变化等）。

#### 11.1 核心结论五件套（每份产出首屏）

1. 一句话结论（≤20 字）+ 一个理由
2. 对我意味着什么（结合持仓/成本）
3. 风险前三条（白话）
4. 价格贵不贵（现价 vs 成本 / vs 历史区间）
5. 下一步可做什么（选项式）+ 不确定性声明

适用于研报、简报、风险体检三类产出；专家模式才展开全部维度。

#### 11.2 专业维度处置清单

| 维度 | 处置 | 说明 |
|------|------|------|
| 四维评分明细 | 精简 | 首屏总分+一句话结论，维度明细折叠 |
| 事后核对 PIT | 改普通版摘要 | 「当时的判断，到现在对了吗」 |
| 研究时间线 delta | 精简 | 保留「观点变化」标记，隐藏分数增量 |
| 因子筛选数值 | 加强解释 | 每条命中附白话点评 |
| 净值曲线 | 加强解释 | 「投 100 变 X 块 vs 大盘 Y 块」 |
| 研究雷达/缺口补跑/配置偏差 | 后置 | 收进设置或专家模式 |
| `partial` 技术文案 | 改普通版 | 「数据还在准备中，稍后再看」 |

#### 11.3 金融词典增强

现有 125 条四字段（short/def/analogy/context_template）+ `<term>` 标注 + TermPopover 弹窗。增强：
- 范围从 chat/简报 扩到研报、风险体检、筛选结果、告警文案；
- 优先补录本项目高频自产词：估值分位、动量、风险敞口、预约披露、事后核对/PIT、已实现盈亏、止盈 等；
- 风格：简版（≤15 字弹窗标题）+ 普通版（2–3 句必含“对你意味着什么”）+ 类比（生活化不轻浮）；
- 入库 lint：analogy 必填、def 不得含未收录术语、禁用网络烂梗/夸张感叹。

#### 11.4 分阶段实施

| 阶段 | 目标 | 关键任务 | 验收 |
|------|------|----------|------|
| **S1** | 研报白话化 + 词库扩域 | 研报链路接入 reading_mode（`output_style_scope`）；research 缓存 key 加 reading_mode；研报返回过 `mark_terms`；`advisor_plain_language.md` 升级；词典补录 | friendly 档新研报无未解释术语连排；术语可弹窗；friendly/professional 缓存不串 |
| **S2** | 专业/普通一键切换 | `report_plain_versions` 缓存表 + `POST /research/reports/{id}/plain` + 前端双态按钮 + 失败降级（显示专业版+提示） | 首次 <10s、二次 <200ms；失败不阻塞 |
| **S3** | 全域通俗化扫尾 | 简报/体检补 reading_mode；持仓盈亏/事件日历/筛选器静态规则白话；`partial` 文案翻新；风险问卷（5 题自动定档 risk_tolerance）；告警白话+下一步 | 九域过新手视角 checklist；零技术黑话 |
| **S4** | 引导与信任 | 新手带练 Onboarding（demo 标的走一遍流程）；场景化知识卡片 | 新用户 5 分钟出第一份看得懂的研报 |

## 九、工程

```bash
uv run uvicorn stockresearch.api.app:app --reload --host 127.0.0.1 --port 8000 --app-dir src
cd web && npm run dev   # :5174
uv run pytest && cd web && npm run build

# 桌面壳（需先 npm run build 前端；本机已装 Rust + uv）
cd desktop && npm install && npm run tauri dev
```

## 十、版本记录

| 版本 | 日期 | 说明 |
|------|------|------|
| **V10.22** | 2026-08-04 | 删除大师/辩论全链路（决策：不迷信大师——不新增且移除既有功能）：后端删除多空辩论与大师点评流水线（`master_commentary` 模块、research/risk 流 `debate_round`/`vote_tally`/`manager` 事件、`skill_bull_bear_debate`/`skill_master_commentary`、`prompts/masters/*`、模式设置 `enable_debate`/`enable_master_commentary`/`selected_masters`/`custom_masters`）；前端删除 debateText 与辩论/大师卡片及设置项；保留风控裁判（judge）汇总与中立表述；§二/§四/4.1/Phase 10/11 相关描述同步收敛；测试与 PRD 同步清理 |
| **V10.21** | 2026-08-04 | 普通用户化第二批（Phase 11 S2-S4）：①单篇普通版切换——`report_plain_versions` 缓存表（迁移 005）+ `POST /research/reports/{id}/plain`（friendly 档并行改写，全字段失败降级返回专业版原文+提示，二次命中缓存）+ 研报详情双态按钮（专业版/普通版）；②简报/体检返回层接词库 `mark_terms`（不污染 DB 原文）；③静态文案扫尾——`partial` 硬编码 i18n 化、`card.factorPartial` 翻新「数据不全」、事件日历/告警文案白话（「阈值」→「提醒线」+ 下一步引导）；④风险问卷 10 题精简 5 题自动定档 `risk_tolerance`（5-7 保守/8-11 稳健/12-15 进取）；⑤新手带练横幅（投顾模式首次进入，demo 标的自动发起白话研报）+ 大师点评声明（「AI 模仿大师风格生成，非大师本人观点」） |
| **V10.20** | 2026-08-04 | 普通用户化（Phase 11）启动：`reading_mode` 三档改两档（friendly 普通版/professional 专业版，存量 standard 归一 friendly，前端选项同步收敛）；研报生成链路接入 `reading_mode`（`output_style_scope` 包裹 research 执行）+ research 缓存 key 加入 reading_mode 防串档；研报返回文本接词库 `mark_terms`；`advisor_plain_language.md` 升级为完整普通版风格规范（平实克制/术语首现必解释/数字翻译影响/风险必保留/建议选项式/禁用词）；词典补录高频自产词；PRD 新增 Phase 11 专项（处置清单+词典增强+四阶段实施） |
| **V10.19** | 2026-08-04 | 持仓闭环第二波：①决策日志挂接研报——`trades.report_id`（迁移 004）自动挂接该标的最近一份研报，`GET /portfolio/trades` 返回 `report_date/report_bias`，交易行内显示当时结论偏向标签；②事件日历——`GET /portfolio/events`（财报预约披露 `stock_yysj_em` + 持仓解禁 `stock_restricted_release_queue_em`，6h 缓存，源失败显式 `partial`）；③因子筛选器——`POST /portfolio/screen`（持仓+自选宇宙，20日动量/年化波动/PE分位条件筛选，缺数计 `skipped` 禁编造），lists 栏新增事件日历与因子筛选（低估值/正动量/低波动/组合预设）折叠块 |
| **V10.18** | 2026-08-04 | 持仓闭环第一波：交易流水表 `trades`（含决策备注，决策日志载体）；买入/卖出入口（新增持仓/确认/批量交易）自动落流水；卖出填成交价自动算已实现盈亏；`GET /portfolio/trades`、`GET /portfolio/performance`（交易流水×前复权日线重建组合净值曲线 vs 沪深300，首日归一 100，缺数/近似显式 `partial`）；lists 栏新增净值走势与交易记录折叠块 |
| **V10.17** | 2026-08-04 | 每日扫描/复盘增强：盘前/盘后简报新增行业板块涨跌榜块（持仓所属行业标注），盘后复盘对照当日盘前观点，盘前 prompt 强化「今日关注点」；Phase 6 收尾：自选股批量研究前端入口（≤8，复用轻研报卡）；Phase 7b：缺口一键补跑 `POST /research/refill`（gap 关键词分类定向驱逐缓存后重跑）；Phase 9b：后端 `ChartOverlaySet` schema + Python 趋势线算法 + `GET /market/overlays` + Copilot 画线技能，对话卡片一键上屏；依赖治理：删 langgraph/langchain-core 死依赖（akshare/efinance/tushare 保持主依赖） |
| **V10.16** | 2026-08-04 | PRD 与实现对齐：登记意图路由上下文装配、大盘宏观/外围研究、LLM 错误详情透传、K 线滚轮缩放修复与自动趋势线；Phase 9a 按实际实现修订（水平参考线与 `ChartOverlaySet` 推迟）；§八路线图加实现状态标注（✅/🚧/❌） |
| **V10.15** | 2026-08-01 | Phase 10：深度分析三层（Impact/Pricing/Thesis）去重合并 Phase 6–7a；导出 `deep_analysis`；PIT 横切；明确非 Qlib/非完整 DCF |
| **V10.14** | 2026-07-30 | Phase 9：K 线算法画线层（趋势+水平，≤4）；9a 前端先落地，9b Copilot 复用同 schema |
| **V10.13** | 2026-07-27 | Copilot：仅「+」开新对话线；同窗续问不自动分叉，回合写入同一会话记忆 |
| **V10.12** | 2026-07-26 | Phase 8：Tauri 2 桌面壳（macOS/Windows），启动 uvicorn + 可选 worker |
| **V10.11** | 2026-07-25 | Phase 7：研究复盘时间线、验证/因子加厚、缺口闭环、研究雷达、配置偏差、CLI/MCP（7a→7c，非交易） |
| **V10.10** | 2026-07-22 | Phase 6：JSON/CSV 导出、PIT 核对声明、自选对比/批量、事件研究、假设一键验证 |
| **V10.9** | 2026-07-20 | §4.1 分析深度档（standard/comprehensive/deep）为四维预算；新闻/财报明确为四维内证据；§5.3 增补质量/成长因子；§八 Phase 5 P0–P3 |
| V10.8 | 2026-07-16 | §七 补登记调度器跨进程互斥机制（文件锁）；§5.1 K 线默认 AkShare 优先对齐代码现状 |
| **V10.7** | 2026-07-14 | §四 补登记「大师点评」为正式特性；风控 `enable_llm_analysis` 可选开关语义写明 |
| **V10.6** | 2026-07-13 | 投研/投顾可靠性：qfq 日线仓、证据因子条、验证分列与事后核对、纸上冲击假设 |
| V10.5 | 2026-07-13 | README 纳入最新 UI 截图（`docs/screenshots/`） |
| V10.4 | 2026-07-11 | 方向：深度证据 + 轻量可验证；Phase 3/4 路线图；公告研报进主链路；数值因子与研究验证语义 |
| V10.3 | 2026-07-07 | 新增独立「市场」Tab；prompts 外置；定时任务独立 worker CLI；新闻 ingest 后台 job；盘前/盘中/盘后三段简报 |
| V10.2 | 2026-07-01 | 精简 PRD；数据源按代码现状重写（新浪/AkShare/efinance 三层行情；K 线 AkShare 优先） |
| V10.1 | 2026-06-30 | 双模式契约；合规语言；Focus 多 Tab；§7 开关语义 |
| V10.0 | 2026-06-29 | 唯一 PRD；三 Tab tri-shell；统一 chat 路由 |
