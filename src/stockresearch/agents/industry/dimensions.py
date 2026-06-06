"""Sector-level dimension prepare/build — policy, capital, valuation, technical, structure."""

from stockresearch.agents.industry.context import SectorResearchContext
from stockresearch.agents.research.agents._scoring import as_confidence
from stockresearch.agents.voice import AGENT_VOICE
from stockresearch.core.constants import CONFIDENCE_LOW, CONFIDENCE_MEDIUM
from stockresearch.core.schemas import DimensionResult

_SUFFIX = f"{AGENT_VOICE} 分析 A 股行业板块，不要给出买卖建议。"


def _board_change(ctx: SectorResearchContext) -> float:
    if ctx.board is None:
        return 0.0
    return ctx.board.change_pct


async def prepare_policy(ctx: SectorResearchContext) -> tuple[str, str, dict[str, object]]:
    news = "\n".join(f"- {line}" for line in ctx.news_snippets[:6]) or "暂无板块相关快讯"
    system = f"你是 A 股行业政策与舆情分析师。{_SUFFIX}"
    user = (
        f"板块：{ctx.sector}\n用户问题：{ctx.query}\n\n"
        f"相关快讯：\n{news}"
    )
    return system, user, {"news_count": len(ctx.news_snippets)}


def build_policy(data: dict[str, object], analysis: str) -> DimensionResult:
    count = int(data.get("news_count", 0))
    score = 5.5 if count >= 3 else 5.0 if count else 4.5
    return DimensionResult(
        agent="policy",
        score=round(min(10.0, max(1.0, score)), 1),
        confidence=as_confidence(CONFIDENCE_MEDIUM if count else CONFIDENCE_LOW),
        highlights=[analysis.strip()] if analysis.strip() else ["板块舆情数据有限"],
        risks=["快讯覆盖可能不完整，需交叉验证政策来源"],
        data_sources=["sector_news"],
    )


async def prepare_capital(ctx: SectorResearchContext) -> tuple[str, str, dict[str, object]]:
    change = _board_change(ctx)
    leader_lines = [
        f"{ld.name}({ld.symbol}) {ld.change_pct:+.2f}%"
        for ld in ctx.leaders[:3]
    ]
    system = f"你是 A 股板块资金与强弱分析师。{_SUFFIX}"
    user = (
        f"板块：{ctx.sector}\n板块涨跌幅：{change:+.2f}%\n"
        f"领涨标的：{'; '.join(leader_lines) or '暂无'}\n"
        f"用户问题：{ctx.query}"
    )
    return system, user, {"board_change": change, "leader_changes": [ld.change_pct for ld in ctx.leaders]}


def build_capital(data: dict[str, object], analysis: str) -> DimensionResult:
    change = float(data.get("board_change", 0))
    score = 5.0
    if change > 1.0:
        score += 1.5
    elif change > 0.3:
        score += 0.8
    elif change < -1.0:
        score -= 1.5
    elif change < -0.3:
        score -= 0.8
    score = max(1.0, min(10.0, score))
    return DimensionResult(
        agent="capital",
        score=round(score, 1),
        confidence=as_confidence(CONFIDENCE_MEDIUM),
        highlights=[analysis.strip()] if analysis.strip() else [f"板块涨跌约 {change:+.2f}%"],
        risks=["单日资金流不代表中期主线"],
        data_sources=["eastmoney_sector_board"],
    )


async def prepare_valuation(ctx: SectorResearchContext) -> tuple[str, str, dict[str, object]]:
    leaders = ", ".join(f"{ld.name}({ld.symbol})" for ld in ctx.leaders[:3]) or "暂无龙头"
    system = f"你是 A 股行业估值与景气分析师。{_SUFFIX}"
    user = f"板块：{ctx.sector}\n龙头/代表股：{leaders}\n用户问题：{ctx.query}"
    return system, user, {"leader_count": len(ctx.leaders)}


def build_valuation(data: dict[str, object], analysis: str) -> DimensionResult:
    count = int(data.get("leader_count", 0))
    score = 5.5 if count >= 2 else 5.0
    return DimensionResult(
        agent="valuation",
        score=round(score, 1),
        confidence=as_confidence(CONFIDENCE_MEDIUM if count else CONFIDENCE_LOW),
        highlights=[analysis.strip()] if analysis.strip() else ["龙头估值需结合财报进一步核实"],
        risks=["板块估值分化大，龙头不代表全行业"],
        data_sources=["sector_leaders"],
    )


async def prepare_technical(ctx: SectorResearchContext) -> tuple[str, str, dict[str, object]]:
    change = _board_change(ctx)
    leader_avg = 0.0
    if ctx.leaders:
        leader_avg = sum(ld.change_pct for ld in ctx.leaders) / len(ctx.leaders)
    system = f"你是 A 股板块技术走势分析师。{_SUFFIX}"
    user = (
        f"板块：{ctx.sector}\n板块涨跌：{change:+.2f}%\n"
        f"龙头平均涨跌：{leader_avg:+.2f}%\n用户问题：{ctx.query}"
    )
    return system, user, {"board_change": change, "leader_avg": leader_avg}


def build_technical(data: dict[str, object], analysis: str) -> DimensionResult:
    change = float(data.get("board_change", 0))
    avg = float(data.get("leader_avg", 0))
    score = 5.0
    if change > 0 and avg > 0:
        score += 1.2
    if change < 0 and avg < 0:
        score -= 1.2
    score = max(1.0, min(10.0, score))
    return DimensionResult(
        agent="technical",
        score=round(score, 1),
        confidence=as_confidence(CONFIDENCE_MEDIUM),
        highlights=[analysis.strip()] if analysis.strip() else [f"板块技术方向 {'偏强' if change > 0 else '偏弱' if change < 0 else '震荡'}"],
        risks=["板块指数与个股走势可能背离"],
        data_sources=["sector_board", "leader_quotes"],
    )


async def prepare_structure(ctx: SectorResearchContext) -> tuple[str, str, dict[str, object]]:
    holdings = "\n".join(ctx.holding_lines) or "用户持仓中暂无该板块标的"
    system = f"你是 A 股板块结构与持仓匹配分析师。{_SUFFIX}"
    user = (
        f"板块：{ctx.sector}\n用户持仓（同业）：\n{holdings}\n"
        f"龙头：{', '.join(ld.name for ld in ctx.leaders[:3]) or '暂无'}\n"
        f"用户问题：{ctx.query}"
    )
    return system, user, {"holding_count": len(ctx.holding_lines)}


def build_structure(data: dict[str, object], analysis: str) -> DimensionResult:
    count = int(data.get("holding_count", 0))
    score = 5.8 if count else 5.0
    return DimensionResult(
        agent="structure",
        score=round(score, 1),
        confidence=as_confidence(CONFIDENCE_MEDIUM),
        highlights=[analysis.strip()] if analysis.strip() else ["关注板块内龙头与跟风分化"],
        risks=["持仓集中度提升会放大板块波动"],
        data_sources=["user_holdings", "sector_leaders"],
    )
