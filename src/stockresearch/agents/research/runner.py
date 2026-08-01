"""Research sub-agents orchestration — delegates to isolated ReAct agents."""

import asyncio
import logging
from typing import Literal

from stockresearch.agents.research.agents import AGENT_BY_ID, DIMENSION_AGENTS
from stockresearch.agents.research.budget import (
    AnalysisDepth,
    budget_for_depth,
    resolve_analysis_depth,
)
from stockresearch.agents.research.context import ResearchContext
from stockresearch.agents.research.debate import run_debate
from stockresearch.agents.research.react import (
    DimensionAgent,
    prepare_react_agent,
    run_react_agent,
)
from stockresearch.agents.master_commentary.context import build_research_context
from stockresearch.agents.master_commentary.stream import get_master_commentary
from stockresearch.agents.research.report_builder import build_research_report
from stockresearch.agents.master_commentary.registry import resolve_master_ids
from stockresearch.core.schemas import (
    DebateResult,
    DimensionResult,
    MasterCommentaryItem,
    ModeSettingsOut,
    ResearchReportOut,
)
from stockresearch.agents.research.scoring import score_bias, weighted_composite_score
from stockresearch.services.factors import factor_alignment_note
from stockresearch.services.text_factor import build_news_text_factor, fetch_symbol_news_snippets
from stockresearch.utils.llm import LLMClient, get_llm_client
from stockresearch.utils.symbols import resolve_name

logger = logging.getLogger(__name__)

BiasLevel = Literal["bullish", "bearish", "neutral"]
ConfidenceLevel = Literal["high", "medium", "low"]


async def prepare_fundamental(ctx: ResearchContext) -> tuple[str, str, dict[str, object]]:
    return await prepare_react_agent(AGENT_BY_ID["fundamental"], ctx)


def build_fundamental(data: dict[str, object], analysis: str) -> DimensionResult:
    return AGENT_BY_ID["fundamental"].build(data, analysis)


async def prepare_technical(ctx: ResearchContext) -> tuple[str, str, dict[str, object]]:
    return await prepare_react_agent(AGENT_BY_ID["technical"], ctx)


def build_technical(data: dict[str, object], analysis: str) -> DimensionResult:
    return AGENT_BY_ID["technical"].build(data, analysis)


async def prepare_sentiment(ctx: ResearchContext) -> tuple[str, str, dict[str, object]]:
    return await prepare_react_agent(AGENT_BY_ID["sentiment"], ctx)


def build_sentiment(data: dict[str, object], analysis: str) -> DimensionResult:
    return AGENT_BY_ID["sentiment"].build(data, analysis)


async def prepare_chips(ctx: ResearchContext) -> tuple[str, str, dict[str, object]]:
    return await prepare_react_agent(AGENT_BY_ID["chips"], ctx)


def build_chips(data: dict[str, object], analysis: str) -> DimensionResult:
    return AGENT_BY_ID["chips"].build(data, analysis)


async def _run_agent(agent: DimensionAgent, ctx: ResearchContext) -> DimensionResult:
    return await run_react_agent(agent, ctx)


async def run_research(
    symbol: str,
    llm: LLMClient | None = None,
    *,
    with_debate: bool = True,
    enable_master_commentary: bool = False,
    mode_settings: ModeSettingsOut | None = None,
    master_ids: list[str] | None = None,
    analysis_depth: AnalysisDepth | str | None = None,
) -> ResearchReportOut:
    client = llm or get_llm_client()
    depth = resolve_analysis_depth(
        explicit=analysis_depth,
        settings_depth=mode_settings.analysis_depth if mode_settings else None,
    )
    budget = budget_for_depth(depth)
    ctx = ResearchContext(symbol=symbol, llm=client, budget=budget)
    name = resolve_name(symbol)

    results = await asyncio.gather(*(_run_agent(agent, ctx) for agent in DIMENSION_AGENTS))
    dimensions = {agent.agent_id: result for agent, result in zip(DIMENSION_AGENTS, results, strict=True)}

    news_snippets = await fetch_symbol_news_snippets(symbol, name)
    news_text_factor = build_news_text_factor(news_snippets, subject=f"{name}({symbol})")

    factors: list = []
    bars_provenance = None
    try:
        from stockresearch.services.factors import compute_numeric_factors

        factors, bars_provenance = await compute_numeric_factors(
            symbol, factor_keys=budget.factor_keys
        )
    except Exception:
        logger.warning("numeric factors failed for %s", symbol, exc_info=True)
        factors = []

    debate: DebateResult | None = None
    if with_debate:
        debate = await run_debate(symbol, name, dimensions, client)

    composite, _ = weighted_composite_score(dimensions)
    bias_for_factors = debate.final_bias if debate is not None else score_bias(composite)
    alignment = (
        factor_alignment_note(bias_for_factors, factors)
        if budget.factors_expanded and factors
        else None
    )

    _LABELS = {
        "fundamental": "基本面",
        "technical": "技术面",
        "sentiment": "情绪面",
        "chips": "筹码面",
    }
    report = build_research_report(
        symbol,
        name,
        dimensions,
        debate,
        dimension_labels=_LABELS,
        news_text_factor=news_text_factor,
        factors=factors,
        bars_provenance=bars_provenance,
        analysis_depth=budget.depth,
        factors_expanded=budget.factors_expanded,
        factor_alignment_note=alignment,
        enable_signal_verify_hook=budget.enable_signal_verify_hook,
    )

    if budget.depth in ("deep", "comprehensive"):
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
    if budget.depth == "deep":
        try:
            from stockresearch.services.pricing_bridge import compute_pricing_bridge

            pricing = await compute_pricing_bridge(symbol, report.factors)
            if report.deep_analysis is None:
                from stockresearch.core.schemas import DeepAnalysisOut

                report.deep_analysis = DeepAnalysisOut(pricing=pricing)
            else:
                report.deep_analysis.pricing = pricing
        except Exception:
            logger.warning("pricing bridge failed for %s", symbol, exc_info=True)

    if enable_master_commentary and mode_settings is not None:
        masters = master_ids or resolve_master_ids(mode_settings)
        commentary = await get_master_commentary(
            client,
            subject=f"{name}({symbol})",
            context=build_research_context(report),
            settings=mode_settings,
            masters=masters,
        )
        report.master_commentary = [
            MasterCommentaryItem.model_validate(item) for item in commentary
        ]

    return report
