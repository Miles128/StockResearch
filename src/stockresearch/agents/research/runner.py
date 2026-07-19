"""Research sub-agents orchestration — delegates to isolated ReAct agents."""

import asyncio
from typing import Literal

from stockresearch.agents.research.agents import AGENT_BY_ID, DIMENSION_AGENTS
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
from stockresearch.services.text_factor import build_news_text_factor, fetch_symbol_news_snippets
from stockresearch.utils.llm import LLMClient, get_llm_client
from stockresearch.utils.symbols import resolve_name

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
) -> ResearchReportOut:
    client = llm or get_llm_client()
    ctx = ResearchContext(symbol=symbol, llm=client)
    name = resolve_name(symbol)

    results = await asyncio.gather(*(_run_agent(agent, ctx) for agent in DIMENSION_AGENTS))
    dimensions = {agent.agent_id: result for agent, result in zip(DIMENSION_AGENTS, results, strict=True)}

    news_snippets = await fetch_symbol_news_snippets(symbol, name)
    news_text_factor = build_news_text_factor(news_snippets, subject=f"{name}({symbol})")

    factors: list = []
    bars_provenance = None
    try:
        from stockresearch.services.factors import compute_numeric_factors

        factors, bars_provenance = await compute_numeric_factors(symbol)
    except Exception:
        factors = []

    debate: DebateResult | None = None
    if with_debate:
        debate = await run_debate(symbol, name, dimensions, client)

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
    )

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
