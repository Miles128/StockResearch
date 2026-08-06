"""Streaming multi-agent research — parallel dimensions + debate + report."""

import asyncio
import logging
from collections.abc import AsyncIterator

from stockresearch.agents.research.battle import iter_battle_events
from stockresearch.agents.research.budget import (
    AnalysisDepth,
    budget_for_depth,
    resolve_analysis_depth,
)
from stockresearch.agents.research.context import ResearchContext
from stockresearch.agents.research.debate import summarize_situation
from stockresearch.agents.research.report_builder import build_research_report
from stockresearch.agents.research.runner import (
    build_chips,
    build_fundamental,
    build_sentiment,
    build_technical,
    prepare_chips,
    prepare_fundamental,
    prepare_sentiment,
    prepare_technical,
)
from stockresearch.agents.research.scoring import score_bias, weighted_composite_score
from stockresearch.agents.stream_typewriter import (
    iter_queue_merged_events,
    pump_dimension_llm_stream,
)
from stockresearch.agents.voice import DEBATE_VOICE
from stockresearch.core.schemas import (
    DebateResult,
    DimensionResult,
    ModeSettingsOut,
    ResearchReportOut,
)
from stockresearch.i18n.status_events import status_event
from stockresearch.services.factors import factor_alignment_note
from stockresearch.services.text_factor import build_news_text_factor, fetch_symbol_news_snippets
from stockresearch.utils.llm import LLMClient, get_llm_client
from stockresearch.utils.symbols import resolve_name

logger = logging.getLogger(__name__)

_BULL_SYSTEM = f"你是看多 Agent。{DEBATE_VOICE}"
_BEAR_SYSTEM = f"你是看空 Agent。{DEBATE_VOICE}"

_AGENT_LABELS: dict[str, str] = {
    "fundamental": "基本面",
    "technical": "技术面",
    "sentiment": "情绪面",
    "chips": "筹码面",
}

_DIMENSION_STREAM_JOBS: list[tuple[str, str, object, object]] = [
    ("fundamental", "基本面", prepare_fundamental, build_fundamental),
    ("technical", "技术面", prepare_technical, build_technical),
    ("sentiment", "情绪面", prepare_sentiment, build_sentiment),
    ("chips", "筹码面", prepare_chips, build_chips),
]


def _dimension_brief(label: str, dim: DimensionResult) -> str:
    parts = [f"{label} {dim.score}/10"]
    parts.extend(dim.highlights)
    if dim.risks:
        parts.append(f"风险：{'；'.join(dim.risks)}")
    return "。".join(parts)


def _build_report(
    symbol: str,
    name: str,
    dimensions: dict[str, DimensionResult],
    debate: DebateResult | None,
    *,
    news_text_factor: str | None = None,
    dimension_labels: dict[str, str] | None = None,
    factors: list | None = None,
    bars_provenance: object | None = None,
    analysis_depth: AnalysisDepth = "standard",
    factors_expanded: bool = False,
    factor_alignment_note: str | None = None,
    enable_signal_verify_hook: bool = False,
) -> ResearchReportOut:
    return build_research_report(
        symbol,
        name,
        dimensions,
        debate,
        dimension_labels=dimension_labels or _AGENT_LABELS,
        news_text_factor=news_text_factor,
        factors=factors,
        bars_provenance=bars_provenance,
        analysis_depth=analysis_depth,
        factors_expanded=factors_expanded,
        factor_alignment_note=factor_alignment_note,
        enable_signal_verify_hook=enable_signal_verify_hook,
    )


async def _attach_deep_analysis(
    report: ResearchReportOut, depth: AnalysisDepth, symbol: str
) -> None:
    """For deep/comprehensive depth, compute Impact; deep-only adds Pricing.

    Both attach with a merge pattern — never replace an existing
    ``DeepAnalysisOut`` (so Impact and Pricing coexist on deep reports).
    """
    if depth in ("deep", "comprehensive"):
        try:
            from stockresearch.core.schemas import DeepAnalysisOut
            from stockresearch.services.impact import compute_impact

            impact = await compute_impact(symbol)
            if report.deep_analysis is None:
                report.deep_analysis = DeepAnalysisOut(impact=impact)
            else:
                report.deep_analysis.impact = impact
        except Exception:
            logger.warning("impact failed for %s", symbol, exc_info=True)

    # Pricing bridge is deep-only: comprehensive keeps Impact per PRD.
    if depth == "deep":
        try:
            from stockresearch.core.schemas import DeepAnalysisOut
            from stockresearch.services.pricing_bridge import compute_pricing_bridge

            pricing = await compute_pricing_bridge(symbol, report.factors)
            if report.deep_analysis is None:
                report.deep_analysis = DeepAnalysisOut(pricing=pricing)
            else:
                report.deep_analysis.pricing = pricing
        except Exception:
            logger.warning("pricing bridge failed for %s", symbol, exc_info=True)

    # Thesis is deep-only and must run AFTER impact + pricing so it can cite them.
    if depth == "deep":
        try:
            from stockresearch.services.thesis_build import build_thesis

            thesis = build_thesis(report)
            if report.deep_analysis is None:
                from stockresearch.core.schemas import DeepAnalysisOut

                report.deep_analysis = DeepAnalysisOut(thesis=thesis)
            else:
                report.deep_analysis.thesis = thesis
        except Exception:
            logger.warning("thesis build failed for %s", symbol, exc_info=True)


async def run_research_stream(
    symbol: str,
    llm: LLMClient | None = None,
    *,
    with_debate: bool = True,
    mode_settings: ModeSettingsOut | None = None,
    analysis_depth: AnalysisDepth | str | None = None,
) -> AsyncIterator[dict[str, object]]:
    client = llm or get_llm_client()
    depth = resolve_analysis_depth(
        explicit=analysis_depth,
        settings_depth=mode_settings.analysis_depth if mode_settings else None,
    )
    budget = budget_for_depth(depth)
    ctx = ResearchContext(symbol=symbol, llm=client, budget=budget)
    name = resolve_name(symbol)

    yield status_event(
        "status.research.start",
        name=name,
        symbol=symbol,
        analysis_depth=budget.depth,
    )

    dimensions: dict[str, DimensionResult] = {}
    queue: asyncio.Queue[object] = asyncio.Queue()
    pumps = [
        asyncio.create_task(
            pump_dimension_llm_stream(
                queue,
                ctx=ctx,
                agent_id=agent_id,
                agent_name=agent_name,
                prepare=prepare,
                build=build,
                dimensions=dimensions,
            )
        )
        for agent_id, agent_name, prepare, build in _DIMENSION_STREAM_JOBS
    ]
    try:
        async for event in iter_queue_merged_events(queue, len(pumps)):
            yield event  # type: ignore[misc]
        await asyncio.gather(*pumps)
    finally:
        # Client disconnect closes the generator mid-loop (GeneratorExit); cancel
        # pump tasks so LLM streams and provider calls stop instead of running on.
        for task in pumps:
            if not task.done():
                task.cancel()
        if pumps:
            await asyncio.gather(*pumps, return_exceptions=True)

    yield status_event("status.research.news_factor")
    news_snippets = await fetch_symbol_news_snippets(symbol, name)
    news_text_factor = build_news_text_factor(news_snippets, subject=f"{name}({symbol})")

    factors: list = []
    bars_provenance = None
    try:
        from stockresearch.services.factors import compute_numeric_factors

        factors, bars_provenance = await compute_numeric_factors(
            symbol, factor_keys=budget.factor_keys
        )
    except Exception as exc:
        logger.warning("numeric factors failed for %s: %s", symbol, exc)

    def _alignment_for(debate: DebateResult | None) -> str | None:
        if not budget.factors_expanded or not factors:
            return None
        if debate is not None:
            return factor_alignment_note(debate.final_bias, factors)
        composite, _ = weighted_composite_score(dimensions)
        return factor_alignment_note(score_bias(composite), factors)

    yield status_event("status.research.summarize")
    if not with_debate:
        report = _build_report(
            symbol,
            name,
            dimensions,
            None,
            news_text_factor=news_text_factor,
            factors=factors,
            bars_provenance=bars_provenance,
            analysis_depth=budget.depth,
            factors_expanded=budget.factors_expanded,
            factor_alignment_note=_alignment_for(None),
            enable_signal_verify_hook=budget.enable_signal_verify_hook,
        )
        await _attach_deep_analysis(report, budget.depth, symbol)
        yield status_event("status.research.report_done")
        yield {"type": "done", "result": report.model_dump(mode="json")}
        return

    situation = summarize_situation(dimensions)
    yield status_event("status.research.battle_start")

    debate_context = f"{name}({symbol})\n作战情报摘要：\n{situation}"
    debate: DebateResult | None = None
    async for event in iter_battle_events(
        client,
        bull_system=_BULL_SYSTEM,
        bear_system=_BEAR_SYSTEM,
        debate_context=debate_context,
        situation=situation,
        dimensions=dimensions,
        agent_labels=_AGENT_LABELS,
    ):
        if event.get("type") == "battle_result":
            debate = event["debate"]  # type: ignore[assignment]
            continue
        yield event

    report = _build_report(
        symbol,
        name,
        dimensions,
        debate,
        news_text_factor=news_text_factor,
        factors=factors,
        bars_provenance=bars_provenance,
        analysis_depth=budget.depth,
        factors_expanded=budget.factors_expanded,
        factor_alignment_note=_alignment_for(debate),
        enable_signal_verify_hook=budget.enable_signal_verify_hook,
    )
    await _attach_deep_analysis(report, budget.depth, symbol)

    yield status_event("status.research.report_done")
    yield {"type": "done", "result": report.model_dump(mode="json")}
