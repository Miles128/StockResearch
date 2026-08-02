# 意图路由驱动的聊天上下文组装 — 设计规格

日期:2026-08-03
状态:已批准(brainstorm 三轮澄清后)
分支:`feat/chat-intent-context`(待建)

## 背景与问题

Copilot 聊天中,市场级提问(如"大盘走势如何")的回答被用户持仓/自选严重污染。根因:上下文组装缺乏统一的意图路由,各注入点各自为政——持仓概况有闸门(`include_holdings`),但新闻排序(`get_news_for_user` 永远按持仓+自选加权)、趋势预取块(`_augment_trend_message`)、SkillRunner 持仓传入都无视 scope。

目标:从头建立"意图判断 → 按域组装上下文"的统一策略。问大盘只给大盘数据,问行业只给行业数据,问持仓只给持仓数据,问个股只给个股数据;分类走"规则优先 + LLM 兜底"双通道。

## 已确认的设计决策

1. **隔离力度**:各域完全隔离。market 意图下持仓/自选对上下文零影响。
2. **分类组合**:规则优先 + LLM 兜底。规则高置信直接定;模糊句才调 LLM。
3. **混合意图**:主意图域为主 + 次要域精简附录块(有长度上限)。
4. **覆盖范围**:全聊天路径(ReAct / Debate / PlanExecute / risk 快捷)统一走一个组装器。

## 架构

### 1. 意图分类器(新模块 `src/stockresearch/services/chat_intent.py`)

```python
ChatIntentKind = Literal["market", "industry", "portfolio", "stock", "general"]

@dataclass(frozen=True)
class ChatIntent:
    primary: ChatIntentKind
    secondary: tuple[ChatIntentKind, ...] = ()   # 混合意图的次要域,最多 1 个
    subject_symbol: str | None = None            # stock 意图的个股代码
    subject_name: str | None = None
    subject_industry: str | None = None          # industry 意图的行业名
    source: Literal["rule", "llm", "fallback"]   # 判定来源,便于观测
```

- **规则层** `classify_by_rule(message) -> ChatIntent | None`:
  复用/扩展 `agents/orchestrator/complexity.py` 的现有判定(`is_market_scope`、`is_holdings_intent`、个股代码/名称提取),补充遗漏模式(如"今天市场""行情如何""A股会涨吗";行业词表复用板块数据)。
  返回 `None` 表示置信不足,交 LLM 兜底。
  优先级:显式个股 > 显式持仓 > 行业 > 大盘 > None。混合句(如"大盘对持仓影响")规则层即可判:primary=portfolio(显式持仓提及优先),secondary=(market,)。
- **LLM 兜底层** `classify_by_llm(message, llm) -> ChatIntent | None`:
  一次轻量调用(temperature 0,短 prompt),要求严格 JSON:`{"primary": "...", "secondary": [...], "subject_symbol": null, "subject_industry": null}`。复用 `extract_json_dict` 解析;解析失败返回 None。
- **入口** `classify_chat_intent(message, llm) -> ChatIntent`:
  规则 → LLM → fallback(`primary="portfolio"` 保持现状行为,source="fallback")。LLM 不可用(Mock 模式/异常/超时)直接跳到 fallback 规则结果,记 warning 日志。

### 2. 统一上下文组装器(重构 `services/chat_scope.py`)

`ChatContextScope` 扩展为携带完整意图:

```python
@dataclass(frozen=True)
class ChatContextScope:
    intent: ChatIntent
    include_holdings: bool          # 由 intent 推导,保留给现有消费点
    holdings: list[Holding]         # market/general 意图下为空列表
    portfolio_tools: bool
    run_portfolio_risk_shortcut: bool
    news_scope: Literal["market", "industry", "personalized", "symbol"]
    subject_symbol: str | None
    subject_name: str | None
```

`build_chat_context_scope(db, user_id, message, llm, ...)` 内部调用 `classify_chat_intent`,是唯一决策点。推导规则:

| primary | include_holdings | news_scope | portfolio_tools | SkillRunner holdings |
|---|---|---|---|---|
| market | False | market | False | [] |
| industry | False | industry | False | [] |
| portfolio | True | personalized | True | 全部 |
| stock | False(除非持仓该股,维持现有逻辑) | symbol | False | 全部 |
| general | False | personalized(降级无害) | False | [] |

次要域附录:secondary 非空时,组装器产出 `secondary_block: str`(有上限:market 附录 ≤ 6 行指数摘要;portfolio 附录 ≤ 6 行持仓摘要;industry 附录 ≤ 4 行板块摘要),作为独立段落附在用户消息后,标题明示(如"【附:你的持仓概况】")。每个 turn 最多 1 个次要域。

### 3. 新闻管线按域过滤(`agents/news/agent.py`、`services/news_interests.py`)

`get_news_for_user(db, user_id, *, related_only, limit, news_scope="personalized", industry=None)`:

- `personalized`:现状(持仓+自选兴趣加权)。
- `market`:跳过 `load_user_news_interests`,不加权,按时间/热度取全市场新闻。
- `industry`:按行业(板块)过滤,不做个股兴趣加权。
- `symbol`:维持现有 symbol 路径。

消费点:`react_agent._tool_news`、`chat_execute._augment_trend_message` 按 scope.news_scope 传参。

### 4. 全路径接入

- `stream.py` / `graph.py`(sync)→ 已经共用 `prepare_chat_turn`,无需各自改动;`prepare_chat_turn` 签名加 `llm` 参数传入分类器。
- ReAct(`react_agent.py`):长期上下文块、工具门控、SkillRunner holdings、`_tool_news` 全部读 scope,不再各自调 `should_include_holdings_context` 等散落判断(这些函数收敛为 scope 推导的内部实现,保留原签名以免大面积改测试,标注 deprecated 内部化)。
- PlanExecute(`plan_execute.py`):用户消息拼接处使用同一 scope 的附录块。
- risk 快捷路径:intent=portfolio 且 run_portfolio_risk_shortcut 才触发(现状逻辑不变,仅改由 intent 推导)。

### 5. Prompt 约束(辅助,非主防线)

`prompts/context_rules.md` 补一条:"回答市场/行业问题时,除非用户明确要求,不引用持仓信息;附录块内容仅在用户问题涉及次要域时引用。"

## 错误处理与降级

- LLM 分类调用任何异常 → warning 日志 + 规则结果/保守 fallback,绝不影响聊天主流程。
- 新闻管线 market 模式下若无新闻数据,返回空块(现有空态处理不变)。
- `news_scope` 参数默认 `personalized`,未改到的调用点行为不变。

## 测试策略

- `tests/services/test_chat_intent.py`:规则层四类 + 混合 + 模糊(返回 None);LLM 层 mock 解析/失败降级;入口优先级。
- `tests/services/test_chat_scope.py`(扩展):各 intent 的 scope 推导(布尔、news_scope、holdings 空否)。
- 新闻:market 模式无持仓加权(构造兴趣数据断言排序)、industry 过滤。
- `react_agent` / `_augment_trend_message`:传参断言(mock)。
- 现有 sync/stream parity、chat_stream 测试保持绿。

## 非目标(YAGNI)

- 不做会话级意图缓存/多轮意图继承(每句独立判定)。
- 不做 industry 意图的专属深度研究 skill(复用现有 INDUSTRY_RESEARCH 路由,本规格只管上下文组装)。
- 不改动简报(briefing)、worker、action-center 的上下文逻辑(它们不走 chat 组装器)。
- LLM 分类不做 fine-tune/embedding,一次性 prompt 即可。
