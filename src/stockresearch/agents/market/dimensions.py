"""Market-level dimension prepare/build — macro, industry, technical, sentiment."""

from stockresearch.agents.market.context import MarketResearchContext
from stockresearch.agents.research.agents._scoring import as_confidence
from stockresearch.agents.voice import AGENT_VOICE
from stockresearch.core.constants import CONFIDENCE_LOW, CONFIDENCE_MEDIUM
from stockresearch.core.schemas import DimensionResult, MarketOverviewOut

_SYSTEM_SUFFIX = (
    f"{AGENT_VOICE} 分析 A 股整体，不要给出买卖建议。"
)


def format_overview_snapshot(overview: MarketOverviewOut) -> str:
    lines: list[str] = []
    for idx in overview.indices:
        arrow = "↑" if idx.change_pct > 0 else "↓" if idx.change_pct < 0 else "→"
        lines.append(f"{idx.name}: {idx.price:.2f} {arrow} {idx.change_pct:+.2f}%")
    if overview.northbound_net_yi is not None:
        direction = "净流入" if overview.northbound_net_yi > 0 else "净流出"
        lines.append(f"北向资金: {abs(overview.northbound_net_yi):.1f}亿 {direction}")
    if overview.advancers is not None and overview.decliners is not None:
        lines.append(f"涨跌家数: {overview.advancers}涨 / {overview.decliners}跌")
    lines.append(f"数据源: {overview.source} ({overview.data_status})")
    return "\n".join(lines) if lines else "市场数据暂不可用"


def _avg_index_change(data: dict[str, object]) -> float:
    changes = data.get("index_changes", [])
    if not isinstance(changes, list) or not changes:
        return 0.0
    return sum(float(x) for x in changes) / len(changes)


async def prepare_macro(ctx: MarketResearchContext) -> tuple[str, str, dict[str, object]]:
    text = ctx.overview_text
    system = f"你是 A 股宏观策略分析师，关注指数、资金面与政策预期。{_SYSTEM_SUFFIX}"
    user = f"用户问题：{ctx.query}\n\n市场快照：\n{text}"
    north = ctx.overview.northbound_net_yi
    changes = [idx.change_pct for idx in ctx.overview.indices]
    return system, user, {"index_changes": changes, "northbound_net_yi": north, "advancers": ctx.overview.advancers}


def build_macro(data: dict[str, object], analysis: str) -> DimensionResult:
    avg = _avg_index_change(data)
    north = data.get("northbound_net_yi")
    score = 5.0
    if avg > 0.5:
        score += 1.0
    if avg < -0.5:
        score -= 1.0
    if isinstance(north, (int, float)) and north > 0:
        score += 0.5
    if isinstance(north, (int, float)) and north < 0:
        score -= 0.5
    score = max(1.0, min(10.0, score))
    return DimensionResult(
        agent="macro",
        score=round(score, 1),
        confidence=as_confidence(CONFIDENCE_MEDIUM),
        highlights=[analysis.strip()] if analysis.strip() else [f"主要指数均涨跌幅约 {avg:+.2f}%"],
        risks=["宏观数据滞后，需结合政策与海外市场"],
        data_sources=["market_overview"],
    )


async def prepare_industry(ctx: MarketResearchContext) -> tuple[str, str, dict[str, object]]:
    text = ctx.overview_text
    adv = ctx.overview.advancers
    dec = ctx.overview.decliners
    breadth = ""
    if adv is not None and dec is not None and adv + dec > 0:
        breadth = f"上涨占比约 {adv / (adv + dec):.0%}"
    system = f"你是 A 股行业轮动分析师，从板块强弱与广度判断结构。{_SYSTEM_SUFFIX}"
    user = f"用户问题：{ctx.query}\n\n市场快照：\n{text}\n{breadth}"
    return system, user, {"advancers": adv, "decliners": dec, "breadth_note": breadth}


def build_industry(data: dict[str, object], analysis: str) -> DimensionResult:
    adv = data.get("advancers")
    dec = data.get("decliners")
    score = 5.0
    if isinstance(adv, int) and isinstance(dec, int) and adv + dec > 0:
        ratio = adv / (adv + dec)
        if ratio > 0.6:
            score += 1.0
        elif ratio < 0.4:
            score -= 1.0
    score = max(1.0, min(10.0, score))
    return DimensionResult(
        agent="industry",
        score=round(score, 1),
        confidence=as_confidence(CONFIDENCE_MEDIUM if adv is not None else CONFIDENCE_LOW),
        highlights=[analysis.strip()] if analysis.strip() else [str(data.get("breadth_note", "结构分化") or "结构分化")],
        risks=["行业轮动快，单日广度不代表中期主线"],
        data_sources=["market_breadth"],
    )


async def prepare_technical(ctx: MarketResearchContext) -> tuple[str, str, dict[str, object]]:
    text = ctx.overview_text
    changes = [idx.change_pct for idx in ctx.overview.indices]
    system = f"你是 A 股指数技术分析师，从主要指数涨跌与趋势判断短期方向。{_SYSTEM_SUFFIX}"
    user = f"用户问题：{ctx.query}\n\n指数表现：\n{text}"
    return system, user, {"index_changes": changes}


def build_technical(data: dict[str, object], analysis: str) -> DimensionResult:
    avg = _avg_index_change(data)
    score = 5.0
    if avg > 0.3:
        score += 1.5
    if avg < -0.3:
        score -= 1.5
    score = max(1.0, min(10.0, score))
    return DimensionResult(
        agent="technical",
        score=round(score, 1),
        confidence=as_confidence(CONFIDENCE_MEDIUM),
        highlights=[analysis.strip()] if analysis.strip() else [f"指数综合方向 {'偏多' if avg > 0 else '偏空' if avg < 0 else '震荡'}"],
        risks=["指数技术面易受权重蓝筹扰动"],
        data_sources=["index_quotes"],
    )


async def prepare_sentiment(ctx: MarketResearchContext) -> tuple[str, str, dict[str, object]]:
    text = ctx.overview_text
    adv = ctx.overview.advancers or 0
    dec = ctx.overview.decliners or 0
    system = f"你是 A 股市场情绪分析师，从涨跌家数、北向与指数波动判断情绪温度。{_SYSTEM_SUFFIX}"
    user = f"用户问题：{ctx.query}\n\n情绪相关数据：\n{text}"
    return system, user, {"advancers": adv, "decliners": dec, "northbound_net_yi": ctx.overview.northbound_net_yi}


def build_sentiment(data: dict[str, object], analysis: str) -> DimensionResult:
    adv = int(data.get("advancers", 0) or 0)
    dec = int(data.get("decliners", 0) or 0)
    total = adv + dec
    score = 5.0
    if total > 0:
        bull_ratio = adv / total
        score = 4.0 + bull_ratio * 6
    north = data.get("northbound_net_yi")
    if isinstance(north, (int, float)) and north < 0:
        score -= 0.5
    if isinstance(north, (int, float)) and north > 0:
        score += 0.5
    score = max(1.0, min(10.0, score))
    return DimensionResult(
        agent="sentiment",
        score=round(score, 1),
        confidence=as_confidence(CONFIDENCE_MEDIUM if total > 0 else CONFIDENCE_LOW),
        highlights=[analysis.strip()] if analysis.strip() else [f"涨跌比 {adv}:{dec}"],
        risks=["情绪指标短期波动大"],
        data_sources=["market_sentiment"],
    )
