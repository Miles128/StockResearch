"""Query complexity classifier — decides direct execution vs Plan-and-Execute."""

import re

from stockresearch.utils.symbols import (
    STOCK_CODE_RE,
    STOCK_NAME_ALTERNATION,
    has_stock_reference,
)

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

_NEWS_INTENT_RE = re.compile(
    r"(新闻|快讯|资讯|消息|报道|头条|发生了什么|怎么回事|公告解读|这条.*新闻|这条.*消息|最近.*消息)"
)

_MARKET_ANALYSIS_RE = re.compile(
    r"(分析|研究|投研|研判|深度|全面|详细|综合|辩论|多空|看法|观点|展望|评估|解读)"
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

_COMPARE_RE = re.compile(r"(对比|比较|vs|versus|哪个更好|哪家|哪只|孰优|优劣)")

# Complex patterns requiring multi-step planning
_COMPLEX_PATTERNS = [
    r"(对比|比较|vs|versus).{2,}",
    r"(组合|portfolio).{0,10}(优化|调整|建议)",
    r"(行业|板块).{0,6}(分析|研究|前景|趋势).{0,6}(和|与|跟).{2,}",
    r"(投资|配置|策略).{0,6}(方案|计划|建议).{0,6}(和|与|跟).{2,}",
    r"(如果|假设|假如).{2,}(会|将|可能).{2,}(那么|则|怎么办)",
    r"(多个|几只|哪些).{0,6}(股票|标的).{0,6}(分析|比较|推荐)",
]

_STOCK_NAMES = f"({STOCK_NAME_ALTERNATION})"

_DEBATE_PATTERNS = [
    r"\d{6}.*?(分析|研究|看法|观点|辩论|持有|还能|继续|值得|买卖)",
    _STOCK_NAMES
    + r".{0,8}(分析|研究|看法|观点|辩论|持有|还能|继续|值得|买卖|怎么样|如何|行不行|好不好)",
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
    INDUSTRY_RESEARCH = "industry_research"


_INDUSTRY_PATTERNS = [
    r"(行业|板块).{0,8}(深度|研究|分析|投研|前景|趋势|研判|怎么样|如何)",
    r"(半导体|新能源|白酒|医药|银行|券商|房地产|消费|科技|军工|光伏|锂电|储能|汽车|传媒|游戏|化工|钢铁|煤炭|有色|电力|通信|计算机|电子|机械|建材|农林|纺织|旅游|航空|航运|保险|信托).{0,6}(行业|板块)",
]

_KNOWN_SECTORS: tuple[str, ...] = (
    "半导体",
    "新能源",
    "白酒",
    "医药",
    "银行",
    "券商",
    "房地产",
    "消费",
    "科技",
    "军工",
    "光伏",
    "锂电",
    "储能",
    "汽车",
    "传媒",
    "化工",
    "钢铁",
    "煤炭",
    "有色",
    "电力",
    "通信",
    "计算机",
    "电子",
)


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

_HOLDINGS_INTENT_RE = re.compile(
    r"(我的|我).{0,8}(持仓|仓位|组合)"
    r"|持仓.{0,12}(分析|看看|怎么样|如何|风险|影响|安全|情况|表现)"
    r"|(组合|portfolio).{0,12}(分析|看看|怎么样|如何|优化|调整|配置)"
    r"|(对|跟|和).{0,8}(我).{0,8}(持仓|仓位|组合)"
    r"|(哪些|哪几).{0,8}持仓"
    r"|持仓里|我持有|我买了|我的自选"
    r"|(帮我|给我).{0,6}(看看|分析).{0,6}(持仓|仓位|组合)"
)

_VAGUE_QUERY_RE = re.compile(
    r"^(分析|看看|怎么样|如何|说说|讲讲|解读|研判|介绍)(一下|下)?$"
    r"|^(你好|嗨|hi|hello|在吗|帮忙)$"
    r"|^请?(分析|解读|说明)(一下|下)?$"
)


_NEWS_EXPLAIN_RE = re.compile(
    r"(解释|解读|说明|讲讲|说说).{0,16}(新闻|消息|快讯|资讯|公告|报道|这条|这篇)"
    r"|(分析下|分析一下).{0,12}(新闻|消息|快讯|资讯|公告|这条|这篇)"
    r"|(这条|这篇|上述|上面|刚才).{0,10}(新闻|消息|快讯|资讯|公告)"
    r"|(新闻|消息|快讯|资讯|公告).{0,16}(什么意思|怎么回事|意味着|代表什么|有何影响|有什么影响|怎么看)"
    r"|(对|跟我|和我).{0,10}(持仓|仓位|组合).{0,16}(影响|关系|怎么办|该如何)"
    r"|有什么影响|怎么回事|发生了什么"
)

_NARROW_SIMPLE_RE = re.compile(
    r"^(什么是|解释|定义|含义|介绍)"
    r"|^(今天|现在|最新|当前).{0,20}(行情|价格|股价|多少钱|新闻|快讯)"
    r"|^(查看|看看|给我).{0,10}(新闻|快讯|行情)"
    r"|\d{6}.{0,8}(多少钱|什么价|现价|报价)"
)


def is_simple_news_explanation(message: str) -> bool:
    """Short news Q&A — direct LLM/ReAct, not multi-agent research."""
    compact = _compact_message(message)
    if _NEWS_EXPLAIN_RE.search(compact):
        return True
    if is_news_intent(message) and len(compact) <= 48 and not wants_deep_research(message):
        if not _MARKET_ANALYSIS_RE.search(compact) and not is_stock_analysis_intent(message):
            return True
    return False


def should_skip_multi_agent(message: str) -> bool:
    """Route to ReAct/simple CoT instead of research, debate, or plan-execute."""
    msg = message.strip()
    if not msg or is_risk_intent(msg):
        return False
    if is_simple_news_explanation(msg):
        return True
    compact = _compact_message(msg)
    if _NARROW_SIMPLE_RE.search(compact):
        return True
    if is_news_intent(msg) and not wants_deep_research(msg):
        if not _MARKET_ANALYSIS_RE.search(compact) and not is_stock_analysis_intent(msg):
            return True
    if len(compact) < 28 and not wants_deep_research(msg):
        if has_stock_reference(msg) and is_stock_analysis_intent(msg):
            return False
        if not re.search(r"(深度|全面|详细|辩论|投研)", compact):
            return True
    return False


def should_skip_debate(message: str) -> bool:
    """Even when debate is enabled, skip for simple or narrow questions."""
    if should_skip_multi_agent(message):
        return True
    compact = _compact_message(message)
    if has_stock_reference(message) and is_stock_analysis_intent(message):
        if wants_deep_research(message) or re.search(r"(分析|研究|投研|怎么看|值不值得)", compact):
            return False
    if len(compact) < 40 and not wants_deep_research(message):
        return True
    if is_news_intent(message) and not wants_deep_research(message):
        return True
    return False


def wants_deep_research(message: str) -> bool:
    return any(kw in message for kw in _DEEP_INTENT_KEYWORDS)


def is_market_scope(message: str) -> bool:
    compact = _compact_message(message)
    if _MARKET_SCOPE_RE.search(compact):
        return True
    return bool(_MARKET_ENTITY_RE.search(compact) and _MARKET_TREND_RE.search(compact))


def count_stock_mentions(message: str) -> int:
    """Distinct stock codes + known names mentioned in the message."""
    codes = set(STOCK_CODE_RE.findall(message))
    names = set(re.findall(_STOCK_NAMES, message))
    return len(codes) + len(names)


def is_stock_comparison(message: str) -> bool:
    """True when the user compares two or more stocks."""
    msg = message.strip()
    if count_stock_mentions(msg) >= 2:
        return True
    return bool(_COMPARE_RE.search(msg) and has_stock_reference(msg))


def count_sector_mentions(message: str) -> int:
    msg = message.strip()
    return sum(1 for sector in _KNOWN_SECTORS if sector in msg)


def is_multi_scope(message: str) -> bool:
    """True when the question spans market + stock/industry, or multiple sectors, etc."""
    msg = message.strip()
    scopes = 0
    if is_market_scope(msg):
        scopes += 1
    if has_stock_reference(msg):
        scopes += 1
    sectors = count_sector_mentions(msg)
    if sectors >= 2:
        return True
    if sectors >= 1 and (is_market_scope(msg) or has_stock_reference(msg)):
        scopes += 1
    if is_industry_research(msg) and (is_market_scope(msg) or has_stock_reference(msg)):
        return True
    return scopes >= 2


def is_single_focus_scope(message: str) -> bool:
    """Only大盘、单股、或单行业/板块 — 不走 Plan-Execute。"""
    msg = message.strip()
    if is_stock_comparison(msg) or is_multi_scope(msg):
        return False
    for pattern in _COMPLEX_PATTERNS:
        if re.search(pattern, msg):
            return False

    if has_stock_reference(msg) and count_stock_mentions(msg) == 1:
        if not is_market_scope(msg) and count_sector_mentions(msg) == 0:
            return True

    if is_market_scope(msg) and not has_stock_reference(msg) and count_sector_mentions(msg) == 0:
        if not is_industry_research(msg):
            return True

    if is_industry_research(msg) and not has_stock_reference(msg) and not is_market_scope(msg):
        if count_sector_mentions(msg) <= 1:
            return True

    return False


def should_auto_plan_execute(message: str) -> bool:
    """Complex queries that must auto-start Plan-and-Execute."""
    msg = message.strip()
    if not msg or is_risk_intent(msg):
        return False

    for pattern in _SIMPLE_PATTERNS:
        if re.search(pattern, msg):
            return False

    if is_single_focus_scope(msg):
        return False

    if is_stock_comparison(msg):
        return True

    for pattern in _COMPLEX_PATTERNS:
        if re.search(pattern, msg):
            return True

    if is_multi_scope(msg):
        return True

    if count_stock_mentions(msg) >= 2:
        return True

    return False


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


def is_holdings_intent(message: str) -> bool:
    """User explicitly asks about their portfolio / holdings."""
    msg = message.strip()
    if not msg:
        return False
    compact = _compact_message(msg)
    if _HOLDINGS_INTENT_RE.search(compact):
        return True
    if "我的持仓" in msg or "我的仓位" in msg or "我的组合" in msg:
        return True
    return False


def is_vague_query(message: str) -> bool:
    """Short/generic prompts without a clear subject — defer to UI context."""
    msg = message.strip()
    if not msg:
        return True
    compact = _compact_message(msg)
    if _VAGUE_QUERY_RE.search(compact):
        return True
    if len(compact) <= 8 and not has_stock_reference(msg) and not is_market_scope(msg):
        return True
    return False


def is_news_intent(message: str) -> bool:
    """True when the user wants news/headlines, not multi-dimensional research."""
    compact = _compact_message(message)
    if _NEWS_INTENT_RE.search(compact):
        return True
    return bool(re.search(r"\bnews\b", compact, re.I))


def is_market_analysis_intent(message: str) -> bool:
    """True when the user wants market-wide research, not a quick snapshot."""
    msg = message.strip()
    if is_news_intent(msg):
        return False
    if not is_market_scope(msg):
        return False
    if wants_deep_research(msg):
        return True
    if _MARKET_ANALYSIS_RE.search(msg):
        return True
    for pattern in _SIMPLE_PATTERNS:
        if re.search(pattern, msg):
            return False
    return False


def is_industry_research(message: str) -> bool:
    msg = message.strip()
    if has_stock_reference(msg):
        return False
    for pattern in _INDUSTRY_PATTERNS:
        if re.search(pattern, msg):
            return True
    return False


def extract_industry_sector(message: str, holding_sectors: list[str] | None = None) -> str | None:
    msg = message.strip()
    for sector in _KNOWN_SECTORS:
        if sector in msg:
            return sector
    m = re.search(r"([^\s，,。！？]{2,8})(行业|板块)", msg)
    if m:
        candidate = m.group(1).strip()
        if candidate and candidate not in ("这个", "那个", "整个", "相关"):
            return candidate
    for sector in holding_sectors or []:
        if sector and sector != "未知" and sector in msg:
            return sector
    return None


_STOCK_ANALYSIS_RE = re.compile(
    r"(分析|研究|投研|走势|基本面|技术面|情绪|筹码|怎么样|如何|咋样|看法|观点|值不值得|能不能买|还能|持有)"
)


def is_stock_analysis_intent(message: str) -> bool:
    """True when the user likely wants per-stock research, not a generic chat reply."""
    msg = message.strip()
    if not msg:
        return False
    if wants_deep_research(msg):
        return True
    if _STOCK_ANALYSIS_RE.search(msg):
        return True
    for pattern in _DEBATE_PATTERNS:
        if re.search(pattern, msg):
            return True
    return False


_STOCK_TREND_EXPLAIN_RE = re.compile(
    r"(走势|涨跌|为什么涨|为什么跌|什么原因|涨了吗|跌了吗|涨了|跌了|"
    r"回调|反弹|拉升|下挫|波动|表现怎么样|今日表现|今天表现|近期表现|"
    r"怎么回事|什么原因|驱动)"
)


def is_trend_explanation_intent(message: str) -> bool:
    """Trend / move questions that need news context without full 4D research."""
    msg = message.strip()
    if not msg or wants_deep_research(msg):
        return False
    compact = _compact_message(msg)
    if has_stock_reference(msg) and _STOCK_TREND_EXPLAIN_RE.search(compact):
        return True
    if is_market_scope(msg) and _MARKET_TREND_RE.search(compact):
        return True
    return False


def classify_research_scope(message: str) -> str | None:
    """Return 'stock' or 'market' only for explicit analysis intents."""
    msg = message.strip()
    if should_skip_multi_agent(msg):
        return None
    if is_news_intent(msg):
        return None
    if has_stock_reference(msg) and is_stock_analysis_intent(msg):
        return "stock"
    if is_market_analysis_intent(msg):
        return "market"
    return None


def resolve_execution_mode(
    message: str,
    *,
    enable_debate: bool = False,
) -> str:
    """Route chat to direct / multi-dim research / debate / plan-execute."""
    msg = message.strip()

    if should_auto_plan_execute(msg):
        return ComplexityResult.PLAN_EXECUTE

    if should_skip_multi_agent(msg):
        return ComplexityResult.DIRECT

    scope = classify_research_scope(msg)
    use_debate = enable_debate and not should_skip_debate(msg)
    if scope == "stock":
        return ComplexityResult.DEBATE if use_debate else ComplexityResult.RESEARCH
    if scope == "market":
        return ComplexityResult.MARKET_DEBATE if use_debate else ComplexityResult.MARKET_RESEARCH

    if is_industry_research(msg):
        return ComplexityResult.INDUSTRY_RESEARCH

    return classify_query(msg)
