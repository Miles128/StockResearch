# StockResearch 产品需求文档

**版本：V10.0 · 开源 A 股市场研究 Agent**

> **唯一 PRD**：`docs/PRD.md`。`docs/` 下仅保留本文件与 `meta.yaml`（`screenshots/` 为 README 配图）。  
> 结构化字段见 `docs/meta.yaml`（供 prd-first 等工具读取）。

---

## 一、产品定位

StockResearch 是**开源的 A 股市场研究 Agent**，在本机联网运行。

不连接券商，不替用户交易，不提供买卖建议。帮助用户理解：**今天发生了什么、为什么与我有关、还需要验证什么**。

## 二、目标用户

### 个人模式

人话、金额、关联原因：持仓相关变化、指标含义、组合可能损失、可继续查看的信息。

### 专家模式

多维指标与来源、四维评分、多空分歧、数据缺口与可验证路径。

两模式共享同一事实与推理，仅改变表达密度。界面统一称 **个人 / 专家**。

## 三、设计原则

1. **AI 是主界面** — 用户描述目标，系统决定查行情、新闻、持仓或启动投研。
2. **渐进披露** — 结论先行，专业指标可展开；常用功能 ≤2 次点击。
3. **三 Tab 焦点** — 中心区仅 **焦点 / 风控 / 新闻**；市场能力并入焦点，不做第四 Tab。
4. **事实与推理分离** — 数据失败显式降级；不输出买卖/目标价/仓位指令。
5. **本地可信** — 单用户、SQLite、localhost、BYOK。

## 四、Tri-Shell 界面

```text
┌─ 顶栏：指数 · 搜索 · 模式 · 告警铃 · 数据源 · 设置 ─────────────────────┐
├─ MarketTicker ───────────────────────────────────────────────────────────┤
├ lists-column ──┬─ center: [焦点][风控][新闻] ────┬─ copilot-column ──────┤
│ ListsSidebar   │ StockFocusView / Risk / News    │ Copilot + Chat        │
│ 持仓 · 自选    │ SectorMovers · ActionCenter     │ 多线程 · SSE          │
└────────────────┴─────────────────────────────────┴───────────────────────┘
```

### 4.1 焦点（含行情与持仓）

- ListsSidebar：组合摘要、持仓、自选股；
- 选中股票：K 线、SectorMovers、ActionCenter；
- 顶栏指数点击可在焦点区展开走势。

### 4.2 风控

- 规则告警、集中度、压力情景；VaR/Sharpe 等可折叠；
- 个人模式可展示资产配置建议。

### 4.3 新闻·研报

- 与我相关 / 市场要闻 / AI 研报；
- ingest 可手动触发；规划后台定时入库。

### 4.4 Copilot

- 右侧可调宽、可折叠、多线程；
- 流式展示过程，完成后折叠轨迹保留卡片；
- **同步与流式 `/chat` 共用 `resolve_chat_route()` 路由**（V10 已统一）。

## 五、核心能力

| 能力 | 说明 |
|------|------|
| 四维投研 + 可选辩论 | fundamental / technical / sentiment / chips → SSE |
| 风控体检 | 规则引擎 + 可选 LLM 人话 |
| 新闻过滤 | 三层规则，3s SLA，无 LLM |
| 价格告警 | APScheduler 5min + 库内通知 + PriceAlertBell 轮询 |
| 定时简报 | APScheduler intraday/postmarket |
| Action Center | 规则信号，零 LLM |
| 双模式 | advisor / research + 术语弹窗 |
| BYOK | LLM / Tushare / Bocha 经请求头或 `.env` |

## 六、数据源

| 层级 | 来源 |
|------|------|
| 行情 | 新浪 → AkShare → efinance |
| 新闻 | AkShare + Bocha 兜底 |
| 财务增强 | Tushare Pro（用户 Key，200 元/年档起） |
| 降级 | `partial` / `missing`，禁止 LLM 编造 |

**不做** iFinD / Wind / Choice 万元级终端 API。

## 七、推送与主动触达（规划）

当前：告警/简报写 SQLite，UI **轮询**（非系统 push）。

| 阶段 | 通道 | 说明 |
|------|------|------|
| **P1** | App + **浏览器 Notification** | 价格告警、重大新闻、简报完成；需用户授权 |
| **P2** | **邮件**（外挂 Agent CLI 推送） | StockResearch MCP/CLI 生成摘要 → 用户自配 SMTP/Agent 发出 |
| **P3** | **短信** 等 | 第三方网关，用户自配 Key |
| **远期** | **飞书机器人** 等 | 大后期；需合规评估 |

所有推送带 disclaimer 与数据时间戳，不含买卖指令。

## 八、Phase 2 路线图

| 支柱 | 内容 |
|------|------|
| **闭环** | Settings 接简报/告警开关；ingest 后台化；App 拆分 |
| **数据** | Tushare Registry；JQData 可选 |
| **外化** | `stockresearch` CLI + MCP；Codex/Claude/OpenCode/Kimi Skills |
| **Prompt** | `prompts/` 外置 |

## 九、非功能与合规

- API 含 `disclaimer`；禁止确定性买卖措辞；
- Cron 绑定 API 进程 — 服务未运行则不执行；
- 仅浏览器 BYOK 时，cron LLM 任务需 Settings 明示或跳过。

## 十、工程附录

### 10.1 部署（摘要）

- **本地**：`uv run uvicorn stockresearch.api.app:app --reload --host 127.0.0.1 --port 8000 --app-dir src` + `cd web && npm run dev`
- **Fly.io**：见仓库 `fly.toml`；`main` push 可触发 GitHub Actions

### 10.2 验证

```bash
pytest
cd web && npm run build
```

### 10.3 文档规则

- `docs/` 仅 `PRD.md` + `meta.yaml`（+ `screenshots/`）
- 禁止在根目录、`documents/`、`.prd/` 另建 PRD
- 产品变更更新 §十一 版本记录

## 十一、版本记录

| 版本 | 日期 | 说明 |
|------|------|------|
| **V10.0** | 2026-06-29 | 唯一 PRD；三 Tab tri-shell；删除四视角与历史文档；统一 chat 路由；推送四阶段规划；移除 daily-scan 死代码 |
| V9.0 | 2026-06-28 | 开源定位；自选股、涨跌提醒（归档，细节以 V10 为准） |
