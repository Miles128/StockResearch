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
from stockresearch.core.schemas import DebateResult, DimensionResult, ResearchReportOut
from stockresearch.utils.llm import LLMClient, get_llm_client
from stockresearch.utils.symbols import resolve_name

BiasLevel = Literal["bullish", "bearish", "neutral"]
ConfidenceLevel = Literal["high", "medium", "low"]


def _as_confidence(value: str) -> ConfidenceLevel:
    from stockresearch.agents.research.agents._scoring import as_confidence

    return as_confidence(value)


async def prepare_fundamental(ctx: ResearchContext) -> tuple[str, str, dict[str, object]]:
    return await prepare_react_agent(AGENT_BY_ID["fundamental"], ctx)


def build_fundamental(data: dict[str, object], analysis: str) -> DimensionResult:
    return AGENT_BY_ID["fundamental"].build(data, analysis)


async def run_fundamental(ctx: ResearchContext) -> DimensionResult:
    return await run_react_agent(AGENT_BY_ID["fundamental"], ctx)


async def prepare_technical(ctx: ResearchContext) -> tuple[str, str, dict[str, object]]:
    return await prepare_react_agent(AGENT_BY_ID["technical"], ctx)


def build_technical(data: dict[str, object], analysis: str) -> DimensionResult:
    return AGENT_BY_ID["technical"].build(data, analysis)


async def run_technical(ctx: ResearchContext) -> DimensionResult:
    return await run_react_agent(AGENT_BY_ID["technical"], ctx)


async def prepare_sentiment(ctx: ResearchContext) -> tuple[str, str, dict[str, object]]:
    return await prepare_react_agent(AGENT_BY_ID["sentiment"], ctx)


def build_sentiment(data: dict[str, object], analysis: str) -> DimensionResult:
    return AGENT_BY_ID["sentiment"].build(data, analysis)


async def run_sentiment(ctx: ResearchContext) -> DimensionResult:
    return await run_react_agent(AGENT_BY_ID["sentiment"], ctx)


async def prepare_chips(ctx: ResearchContext) -> tuple[str, str, dict[str, object]]:
    return await prepare_react_agent(AGENT_BY_ID["chips"], ctx)


def build_chips(data: dict[str, object], analysis: str) -> DimensionResult:
    return AGENT_BY_ID["chips"].build(data, analysis)


async def run_chips(ctx: ResearchContext) -> DimensionResult:
    return await run_react_agent(AGENT_BY_ID["chips"], ctx)


async def _run_agent(agent: DimensionAgent, ctx: ResearchContext) -> DimensionResult:
    return await run_react_agent(agent, ctx)


async def run_research(
    symbol: str,
    llm: LLMClient | None = None,
    *,
    with_debate: bool = True,
) -> ResearchReportOut:
    client = llm or get_llm_client()
    ctx = ResearchContext(symbol=symbol, llm=client)
    name = resolve_name(symbol)

    results = await asyncio.gather(*(_run_agent(agent, ctx) for agent in DIMENSION_AGENTS))
    dimensions = {agent.agent_id: result for agent, result in zip(DIMENSION_AGENTS, results, strict=True)}

    fundamental = dimensions["fundamental"]
    technical = dimensions["technical"]
    sentiment = dimensions["sentiment"]
    chips = dimensions["chips"]

    scores = [d.score for d in dimensions.values()]
    composite = round(sum(scores) / len(scores), 1)

    confidences = [_as_confidence(d.confidence) for d in dimensions.values()]
    if confidences.count("high") >= 2:
        composite_confidence: ConfidenceLevel = "high"
    elif "low" in confidences:
        composite_confidence = "low"
    else:
        composite_confidence = "medium"

    if composite >= 6.5:
        bias: BiasLevel = "bullish"
    elif composite <= 4.5:
        bias = "bearish"
    else:
        bias = "neutral"

    summary = (
        f"{name}({symbol}) 综合评分 {composite}/10，"
        f"四维投票倾向{'偏多' if bias == 'bullish' else '偏空' if bias == 'bearish' else '中性'}。"
        f"基本面 {fundamental.score}，技术面 {technical.score}，"
        f"情绪面 {sentiment.score}，筹码面 {chips.score}。"
    )

    debate: DebateResult | None = None
    if with_debate:
        debate = await run_debate(symbol, name, dimensions, client)
        bias_label = (
            "偏多" if debate.final_bias == "bullish"
            else "偏空" if debate.final_bias == "bearish"
            else "中性"
        )
        summary += f" 裁判倾向：{bias_label}。"

    return ResearchReportOut(
        symbol=symbol,
        name=name,
        dimensions=dimensions,
        composite_score=composite,
        composite_confidence=composite_confidence,
        bias=bias,
        summary=summary,
        debate=debate,
    )
