# Kimi Datasource 接入设计

日期:2026-08-01
状态:已获用户批准,待实现

## 背景与目标

StockResearch 现有数据源(新浪/akshare/efinance/Tushare/博查)以 A 股行情与新闻为主。Kimi Datasource(Kimi Code CLI 官方插件,内置 Wind、IMF、World Bank、Gildata、SEC EDGAR、S&P Capital IQ)能补充宏观与行业数据、Wind 深度数据(公告/研报/财务指标)。用户持有 Kimi Code 会员,数据查询按次消耗会员配额。

**已查证的关键约束**(来源:kimi.com/code/docs 官方文档):

- Kimi Datasource 不是独立公开 API,只能在 Kimi Code CLI 内使用,依赖 `/login` 的本地 OAuth 凭证
- 程序化调用方式:`kimi -p "<prompt>" --output-format stream-json` 非交互模式(stdout 每行一个 JSON 对象,auto 权限,无需人工确认)

**目标**:把 Kimi 数据接入项目统一的 provider + 缓存体系,定时预取落库,同时支持用户触发实时查询,分期在简报、market 页、copilot agent、risk 页体现。

## 需求范围(用户已确认)

- 数据类型(第一期):宏观与行业数据、Wind 深度数据(公告/研报/财务指标)
- 调用方式:`kimi -p` 子进程(asyncio subprocess)
- 角色:补充现有源没有的数据 + 定时预取落库 + 用户触发可实时读取
- UI 呈现(分四期):简报内容 → market 页新面板 → agent 研究引用 → risk 页预警

## 架构

```
┌─ worker 进程 ──────────────────────────────┐
│  KimiPrefetchScheduler (新增, 仿 DailyBar)  │
│    交易日 8:20 / 16:20 触发                │
└──────┬─────────────────────────────────────┘
       ▼
┌─ provider 层 ──────────────────────────────┐
│  KimiMacroProvider   (宏观/行业数据)        │
│  KimiWindProvider    (A股公告/研报/深度)    │
│      ↓ 共用                                │
│  KimiCliClient (data/providers/kimi_cli.py)│
│    asyncio subprocess → kimi -p            │
│    --output-format stream-json → 严格 JSON │
│      ↓                                     │
│  provider_cache_policy + sqlite_cache      │
│  (复用现有 provider_cache 表, 不建新表)     │
└──────┬─────────────────────────────────────┘
       ▼
┌─ 消费方 (分期接入) ────────────────────────┐
│  P1 简报  P2 market 面板  P3 agent/risk    │
└────────────────────────────────────────────┘
```

### 新增文件

- `src/stockresearch/data/providers/kimi_cli.py` — `KimiCliClient`:异步子进程封装,超时、重试(最多 2 次,指数退避)、stream-json 解析、错误归类
- `src/stockresearch/data/providers/kimi_macro.py` — `KimiMacroProvider`:GDP/CPI/PMI/利率等宏观与行业指标
- `src/stockresearch/data/providers/kimi_wind.py` — `KimiWindProvider`:公告、研报、Wind 财务指标
- `src/stockresearch/services/kimi_prefetch_scheduler.py` — 定时预取,在 `worker.py:run_worker()` 注册
- `tests/providers/test_kimi_cli.py`、`tests/providers/test_kimi_providers.py`、`tests/services/test_kimi_prefetch_scheduler.py`

### 注册与配置点

- `data/provider_meta.py:PROVIDER_CATALOG` 加 `kimi_macro`、`kimi_wind` 条目(L2 层;宏观 TTL 24h,公告/研报 TTL 6h)
- `core/config.py:Settings` 加字段 + `.env.example` 注释段:
  - `kimi_cli_enabled`(默认 false)
  - `kimi_cli_path`(默认 `kimi`)
  - `kimi_cli_timeout_seconds`(默认 120)
  - `kimi_live_max_calls_per_day`(默认 20)
  - `kimi_prefetch_tasks`(预取任务清单,JSON 配置,第一期限 6-10 条)

## 数据流

### 路径 1:定时预取(批量写缓存)

1. `KimiPrefetchScheduler` 触发(交易日 8:20 / 16:20,`CronTrigger`,复用 `trading_calendar` 跳过非交易日,复用 `scheduler_lock` 保证单进程)
2. 对 `kimi_prefetch_tasks` 中每条任务,`KimiCliClient` 组装要求严格 JSON 输出的 prompt,执行 `kimi -p "<prompt>" --output-format stream-json`
3. 从 stream-json 提取最终 assistant 消息并解析 JSON;失败重试最多 2 次(指数退避),仍失败则等下个调度窗口,不无限重试
4. 成功写入 `provider_cache`(key 含数据类型+日期,TTL 按 provider_meta)
5. 原始响应保留 7 天用于排查解析失败

### 路径 2:用户触发实时查询(缓存优先)

- copilot 工具 `get_macro_data`、`get_wind_announcements` 带 `refresh: bool` 参数:默认读缓存;agent 判断缓存缺失或用户要求"最新"时走实时调用
- market 宏观面板(P2)提供"刷新"按钮,走同一实时路径
- 实时调用期间通过现有 SSE `status` 事件向前端推"正在查询 Kimi 数据源…"进度(单次可能 5-30 秒)
- 实时调用结果同样写缓存(TTL 照旧),短期重复查询不重复扣费

### 配额护栏

- 每日实时调用上限 `kimi_live_max_calls_per_day`(默认 20);超限后降级读缓存并明确告知用户
- 单次 copilot 会话(ReAct 循环)内最多 2 次实时 Kimi 调用
- 预取失败每天最多重试 2 次,等下个调度窗口

### 消费方分期

- **P1 简报增强**:简报生成器在现有数据外多读 `kimi_macro`/`kimi_wind` 缓存,有则纳入,无则跳过(不影响现有简报)
- **P2 market 面板**:`api/routes/market.py` 加 `GET /macro/kimi` 端点返回缓存;前端 market 页加宏观面板,缺数据显示"待预取",带手动刷新按钮
- **P3 agent + risk**:`tools_registry.py` 注册两个工具 + `react_agent.py:_execute_tool` 加分支;risk agent 引用宏观缓存数据做风险预警

## 错误处理

| 场景 | 行为 |
| --- | --- |
| `kimi` CLI 不存在/未登录 | 启动时探测一次(`kimi --version`),失败则 `kimi_cli_enabled` 视为关闭,所有路径静默跳过并在日志记录 |
| 子进程超时(120s) | 杀进程,记一次失败,走重试策略;agent 实时调用超时则回退缓存并说明数据时点 |
| JSON 解析失败 | 记原始响应到排查日志,按失败处理,不写入缓存(复用 `should_persist_provider_dict` 防毒逻辑) |
| 配额/计费报错 | 识别错误类别,当日后续调用直接短路,避免反复扣费 |
| 缓存为空且实时不可用 | 消费方降级:简报跳过该段、面板显示"待预取"、agent 明确告知无数据 |

## 测试

- `test_kimi_cli.py`:mock 子进程,覆盖成功解析、JSON 错误、超时、重试、CLI 缺失
- `test_kimi_providers.py`:两个 provider 的缓存读写与 TTL(mock `KimiCliClient`)
- `test_kimi_prefetch_scheduler.py`:任务枚举、失败重试上限、非交易日跳过
- P2/P3 阶段补 API 端点测试与工具注册测试
- 验收命令:`pytest tests/providers/test_kimi_cli.py tests/providers/test_kimi_providers.py tests/services/test_kimi_prefetch_scheduler.py`;交付前全量 `pytest && cd web && npm run build`
- 不做真实 CLI 调用的自动化测试(消耗配额);手动验证脚本放 `scripts/` 下

## 明确不做(YAGNI)

- 不接美股/SEC/IMF 等其他数据源类型(后续按同一模式扩展)
- 不用 `kimi web` 常驻服务(已选定子进程方案)
- 不建新数据库表(复用 `provider_cache`)
- 前端不做数据可视化重构,宏观面板用现有图表组件
- 不做多用户配额隔离(项目当前单用户)
