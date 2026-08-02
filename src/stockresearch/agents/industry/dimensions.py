"""Sector-level dimension prepare/build — policy, capital, valuation, technical, structure."""

import logging

from stockresearch.agents.industry.context import SectorResearchContext
from stockresearch.agents.research.agents._scoring import as_confidence
from stockresearch.agents.research.dimension_text import REPORT_DIM_VOICE, finalize_dimension
from stockresearch.core.constants import CONFIDENCE_LOW, CONFIDENCE_MEDIUM
from stockresearch.core.schemas import DimensionResult

logger = logging.getLogger(__name__)

_SUFFIX = f"{REPORT_DIM_VOICE} 分析 A 股行业板块。"


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
    return finalize_dimension(
        agent="policy",
        score=min(10.0, max(1.0, score)),
        confidence=as_confidence(CONFIDENCE_MEDIUM if count else CONFIDENCE_LOW),
        raw_analysis=analysis,
        data_sources=["sector_news"],
        fallback_highlights=["板块舆情数据有限"],
        fallback_risks=["快讯覆盖可能不完整，需交叉验证政策来源"],
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
    return finalize_dimension(
        agent="capital",
        score=score,
        confidence=as_confidence(CONFIDENCE_MEDIUM),
        raw_analysis=analysis,
        data_sources=["eastmoney_sector_board"],
        fallback_highlights=[f"板块涨跌约 {change:+.2f}%"],
        fallback_risks=["单日资金流不代表中期主线"],
    )


async def prepare_valuation(ctx: SectorResearchContext) -> tuple[str, str, dict[str, object]]:
    from stockresearch.data.providers.market import FinancialDataProvider

    leaders = ctx.leaders[:3]
    leader_label = ", ".join(f"{ld.name}({ld.symbol})" for ld in leaders) or "暂无龙头"
    provider = FinancialDataProvider()
    valuations: list[dict[str, object]] = []
    for ld in leaders:
        if not ld.symbol:
            continue
        try:
            val = await provider.get_valuation(ld.symbol)
        except Exception:
            logger.debug("leader valuation skipped for %s", ld.symbol, exc_info=True)
            continue
        pe = val.get("pe_ttm")
        pb = val.get("pb")
        pe_pct = val.get("pe_percentile")
        valuations.append(
            {
                "symbol": ld.symbol,
                "name": ld.name,
                "pe_ttm": pe,
                "pb": pb,
                "pe_percentile": pe_pct,
            }
        )

    pe_values = [float(v["pe_ttm"]) for v in valuations if isinstance(v.get("pe_ttm"), (int, float))]
    avg_pe = round(sum(pe_values) / len(pe_values), 2) if pe_values else None
    pe_lines = []
    for v in valuations:
        pe = v.get("pe_ttm")
        pe_pct = v.get("pe_percentile")
        pe_txt = f"PE {pe:.1f}" if isinstance(pe, (int, float)) else "PE 缺失"
        pct_txt = (
            f"历史分位 {float(pe_pct):.0%}"
            if isinstance(pe_pct, (int, float))
            else "分位不可算"
        )
        pe_lines.append(f"- {v['name']}({v['symbol']}): {pe_txt}，{pct_txt}")

    system = f"你是 A 股行业估值与景气分析师。{_SUFFIX}"
    user = (
        f"板块：{ctx.sector}\n龙头/代表股：{leader_label}\n"
        f"龙头估值：\n{chr(10).join(pe_lines) or '暂无可用估值'}\n"
        f"龙头平均 PE：{avg_pe if avg_pe is not None else 'N/A'}\n"
        f"用户问题：{ctx.query}"
    )
    return system, user, {
        "leader_count": len(leaders),
        "valuations": valuations,
        "avg_pe": avg_pe,
        "pe_available": len(pe_values),
    }


def build_valuation(data: dict[str, object], analysis: str) -> DimensionResult:
    count = int(data.get("leader_count", 0))
    pe_available = int(data.get("pe_available", 0))
    avg_pe = data.get("avg_pe")
    score = 5.0
    if pe_available >= 2:
        score += 0.5
    if isinstance(avg_pe, (int, float)):
        if avg_pe < 20:
            score += 0.8
        elif avg_pe > 50:
            score -= 0.5
    elif count >= 2:
        score += 0.3
    score = max(1.0, min(10.0, score))

    gaps: list[str] = []
    if pe_available == 0:
        gaps.append("龙头估值 PE 不可用")
    if isinstance(avg_pe, (int, float)):
        fallback = [f"龙头平均 PE {avg_pe:.1f}（基于 {pe_available} 只）"]
    else:
        fallback = ["龙头估值需结合财报进一步核实"]

    return finalize_dimension(
        agent="valuation",
        score=score,
        confidence=as_confidence(CONFIDENCE_MEDIUM if pe_available else CONFIDENCE_LOW),
        raw_analysis=analysis,
        data_sources=["sector_leaders", "akshare_valuation"] if pe_available else ["sector_leaders"],
        fallback_highlights=fallback,
        fallback_risks=["板块估值分化大，龙头不代表全行业"],
        gaps=gaps,
        partial=bool(gaps),
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
    return finalize_dimension(
        agent="technical",
        score=score,
        confidence=as_confidence(CONFIDENCE_MEDIUM),
        raw_analysis=analysis,
        data_sources=["sector_board", "leader_quotes"],
        fallback_highlights=[
            f"板块技术方向 {'偏强' if change > 0 else '偏弱' if change < 0 else '震荡'}"
        ],
        fallback_risks=["板块指数与个股走势可能背离"],
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
    return finalize_dimension(
        agent="structure",
        score=score,
        confidence=as_confidence(CONFIDENCE_MEDIUM),
        raw_analysis=analysis,
        data_sources=["user_holdings", "sector_leaders"],
        fallback_highlights=["关注板块内龙头与跟风分化"],
        fallback_risks=["持仓集中度提升会放大板块波动"],
    )
