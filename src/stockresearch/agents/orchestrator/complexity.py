"""Query complexity classifier — decides direct execution vs Plan-and-Execute."""

import re

# Deep research / debate intent (stock or market)
_DEEP_INTENT_KEYWORDS: tuple[str, ...] = (
    "辩论",
    "多空",
    "深度分析",
    "深度研究",
    "深度投研",
    "深度研判",
    "投研",
    "全面分析",
    "详细分析",
    "综合研究",
)

_MARKET_SCOPE_RE = re.compile(
    r"(大盘|市场走势|a股走势|股市走势|整体市场|整个市场|宏观走势|指数走势|"
    r"沪指|上证|深证|创业板|沪深300|a股市场|市场方向|大盘方向|沪深市场)"
)

_MARKET_ENTITY_RE = re.compile(
    r"(大盘|沪指|上证|深证|创业板|沪深300|a股|股市|大盘|市场|指数|宏观|沪深市场)"
)

_MARKET_TREND_RE = re.compile(
    r"(走势|行情|方向|趋势|怎么看|如何|怎么样|咋样|向好|看跌|看涨|涨跌|牛熊|研判|展望)"
)


def _compact_message(message: str) -> str:
    """Collapse spaces and normalize for Chinese finance intent matching."""
    msg = message.strip().lower().replace("Ａ", "a")
    return re.sub(r"\s+", "", msg)

# Simple patterns that can be answered directly (skipped when deep intent present)
_SIMPLE_PATTERNS = [
    r"^(你好|嗨|hi|hello|谢谢|感谢)",
    r"^(什么是|解释|定义|含义)",
    r"^(今天|当前|最新).{0,6}(大盘|行情|指数|市场)",
    r"^(查看|获取|给我).{0,6}(新闻|快讯|行情)",
    r"\d{6}.*?(行情|价格|报价)",
]

# Complex patterns requiring multi-step planning
_COMPLEX_PATTERNS = [
    r"(对比|比较|vs|versus).{2,}",
    r"(组合|portfolio).{0,10}(优化|调整|建议)",
    r"(行业|板块).{0,6}(分析|研究|前景|趋势).{0,6}(和|与|跟).{2,}",
    r"(投资|配置|策略).{0,6}(方案|计划|建议).{0,6}(和|与|跟).{2,}",
    r"(如果|假设|假如).{2,}(会|将|可能).{2,}(那么|则|怎么办)",
    r"(多个|几只|哪些).{0,6}(股票|标的).{0,6}(分析|比较|推荐)",
]

_STOCK_NAMES = (
    r"(茅台|宁德时代|宁德|比亚迪|招商银行|招行|平安|中芯国际|中芯"
    r"|腾讯|阿里|阿里巴巴|五粮液|泸州老窖|恒瑞医药|美的|格力"
    r"|中国平安|工商银行|建行|农行|中行|交行|兴业|浦发|民生"
    r"|海康威视|药明康德|隆基绿能|隆基|通威|紫金矿业|长江电力"
    r"|中国移动|中国石油|中国石化|神华|中远海控)"
)

_DEBATE_PATTERNS = [
    r"\d{6}.*?(分析|研究|看法|观点|辩论|持有|还能|继续|值得|买卖)",
    _STOCK_NAMES + r".{0,8}(分析|研究|看法|观点|辩论|持有|还能|继续|值得|买卖|怎么样|如何|行不行|好不好)",
    r"(这只|这个|那只|那只).{0,4}(股票|股).{0,4}(怎么样|如何|值不值得|能不能买|还能|持有|继续)",
    r"\d{6}.*?(财报|比率|PE|PB|ROE|毛利率|净利率|市盈率|市净率|估值)",
    _STOCK_NAMES + r".{0,6}(财报|比率|PE|PB|ROE|毛利率|净利率|市盈率|市净率|估值)",
    r"(深度|详细|全面).{0,4}(分析|研究).{0,4}\d{6}",
    r"\d{6}.{0,6}(深度|详细|全面).{0,4}(分析|研究)",
    _STOCK_NAMES + r"(还能|可以|值得|继续).{0,4}(持有|买|卖|拿|留)",
    r"\d{6}.{0,4}(吗|呢|？|\?)",
]


class ComplexityResult:
    """Result of complexity classification."""

    DIRECT = "direct"
    RESEARCH = "research"
    MARKET_RESEARCH = "market_research"
    DEBATE = "debate"
    MARKET_DEBATE = "market_debate"
    PLAN_EXECUTE = "plan_execute"


ANALYSIS_SIMPLE = "simple"
ANALYSIS_COMPLEX = "complex"

_RISK_KEYWORDS: tuple[str, ...] = (
    "风险",
    "止损",
    "仓位",
    "体检",
    "回撤",
    "持仓安全",
    "危险",
)


def wants_deep_research(message: str) -> bool:
    return any(kw in message for kw in _DEEP_INTENT_KEYWORDS)


def is_market_scope(message: str) -> bool:
    compact = _compact_message(message)
    if _MARKET_SCOPE_RE.search(compact):
        return True
    return bool(_MARKET_ENTITY_RE.search(compact) and _MARKET_TREND_RE.search(compact))


_STOCK_CODE_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")


def has_stock_reference(message: str) -> bool:
    if _STOCK_CODE_RE.search(message):
        return True
    return bool(re.search(_STOCK_NAMES, message))


def classify_query(message: str) -> str:
    """Classify query complexity and return execution strategy."""
    msg = message.strip()
    deep = wants_deep_research(msg)
    market = is_market_scope(msg)
    stock = has_stock_reference(msg)

    # 大盘 + 深度/辩论/投研 → 市场多空辩论流
    if deep and market and not stock:
        return ComplexityResult.MARKET_DEBATE

    # 深度投研但未点名个股，且涉及市场/走势 → 市场辩论
    if deep and not stock and re.search(r"(市场|行情|走势|宏观|指数)", msg):
        return ComplexityResult.MARKET_DEBATE

    # 个股辩论 / 深度投研
    if deep and stock:
        return ComplexityResult.DEBATE
    for pattern in _DEBATE_PATTERNS:
        if re.search(pattern, msg):
            return ComplexityResult.DEBATE

    for pattern in _COMPLEX_PATTERNS:
        if re.search(pattern, msg):
            return ComplexityResult.PLAN_EXECUTE

    if not deep:
        for pattern in _SIMPLE_PATTERNS:
            if re.search(pattern, msg):
                return ComplexityResult.DIRECT

    if len(msg) < 15:
        return ComplexityResult.DIRECT

    return ComplexityResult.PLAN_EXECUTE


def is_risk_intent(message: str) -> bool:
    return any(kw in message for kw in _RISK_KEYWORDS)


def classify_research_scope(message: str) -> str | None:
    """Return 'stock' or 'market' when the query is finance-research scoped."""
    msg = message.strip()
    if has_stock_reference(msg):
        return "stock"
    if is_market_scope(msg):
        return "market"
    compact = _compact_message(msg)
    if _MARKET_ENTITY_RE.search(compact) and _MARKET_TREND_RE.search(compact):
        return "market"
    return None


def resolve_execution_mode(
    message: str,
    analysis_mode: str | None = None,
    *,
    enable_debate: bool = False,
) -> str:
    """Route chat to direct / multi-dim research / debate / plan-execute."""
    msg = message.strip()

    # Legacy clients may still send simple/complex — honor simple only.
    if analysis_mode == ANALYSIS_SIMPLE:
        return ComplexityResult.DIRECT

    for pattern in _COMPLEX_PATTERNS:
        if re.search(pattern, msg):
            return ComplexityResult.PLAN_EXECUTE

    scope = classify_research_scope(msg)
    if scope == "stock":
        return ComplexityResult.DEBATE if enable_debate else ComplexityResult.RESEARCH
    if scope == "market":
        return ComplexityResult.MARKET_DEBATE if enable_debate else ComplexityResult.MARKET_RESEARCH

    if analysis_mode == ANALYSIS_COMPLEX:
        auto = classify_query(msg)
        if auto in (ComplexityResult.DEBATE, ComplexityResult.MARKET_DEBATE):
            return auto if enable_debate else (
                ComplexityResult.RESEARCH
                if auto == ComplexityResult.DEBATE
                else ComplexityResult.MARKET_RESEARCH
            )
        if auto == ComplexityResult.PLAN_EXECUTE:
            return ComplexityResult.PLAN_EXECUTE

    return classify_query(msg)
