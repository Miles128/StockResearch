"""Streaming market-wide research — macro/industry/technical/sentiment + bull/bear debate."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from stockresearch.agents.market.context import MARKET_NAME, MARKET_SYMBOL, MarketResearchContext
from stockresearch.agents.market.dimensions import (
    build_industry,
    build_macro,
    build_sentiment,
    build_technical,
    format_enrichment_block,
    format_overview_snapshot,
    prepare_industry,
    prepare_macro,
    prepare_sentiment,
    prepare_technical,
)
from stockresearch.agents.master_commentary.context import build_market_context
from stockresearch.agents.master_commentary.registry import resolve_master_ids
from stockresearch.agents.master_commentary.stream import stream_master_commentary
from stockresearch.agents.research.battle import iter_battle_events
from stockresearch.agents.research.debate import summarize_situation
from stockresearch.agents.research.report_builder import build_research_report
from stockresearch.agents.stream_typewriter import (
    iter_queue_merged_events,
    pump_dimension_llm_stream,
)
from stockresearch.agents.voice import DEBATE_VOICE
from stockresearch.core.schemas import (
    DebateResult,
    DimensionResult,
    MasterCommentaryItem,
    ModeSettingsOut,
)
from stockresearch.data.providers.global_markets import (
    GlobalMarketsProvider,
    format_global_snapshot,
)
from stockresearch.data.providers.market_overview import MarketOverviewProvider
from stockresearch.i18n.status_events import status_event
from stockresearch.services.macro_snapshot import format_macro_snapshot
from stockresearch.services.text_factor import build_news_text_factor, fetch_market_news_snippets
from stockresearch.utils.llm import LLMClient, get_llm_client

_BULL_SYSTEM = f"你是 A 股大盘看多分析师（Bull Agent）。{DEBATE_VOICE} 基于宏观/行业/技术/情绪四维，阐述看多逻辑。"
_BEAR_SYSTEM = f"你是 A 股大盘看空分析师（Bear Agent）。{DEBATE_VOICE} 指出下行风险与逻辑漏洞。"

_AGENT_LABELS: dict[str, str] = {
    "macro": "宏观面",
    "industry": "行业面",
    "technical": "技术面",
    "sentiment": "情绪面",
}

_DIMENSION_JOBS: list[tuple[str, str, object, object]] = [
    ("macro", "宏观面", prepare_macro, build_macro),
    ("industry", "行业面", prepare_industry, build_industry),
    ("technical", "技术面", prepare_technical, build_technical),
    ("sentiment", "情绪面", prepare_sentiment, build_sentiment),
]


async def run_market_research_stream(
    query: str,
    llm: LLMClient | None = None,
    *,
    with_debate: bool = True,
    enable_master_commentary: bool = False,
    mode_settings: ModeSettingsOut | None = None,
    master_ids: list[str] | None = None,
) -> AsyncIterator[dict[str, object]]:
    """Market deep research with the same bull/bear + judge flow as stock research."""
    client = llm or get_llm_client()
    provider = MarketOverviewProvider()
    global_provider = GlobalMarketsProvider()
    overview, global_rows = await asyncio.gather(
        provider.get_overview(),
        global_provider.get_indices(),
    )
    overview_text = format_overview_snapshot(overview)
    global_text = format_global_snapshot(global_rows)
    macro_text = format_macro_snapshot()
    ctx = MarketResearchContext(
        query=query,
        llm=client,
        overview=overview,
        overview_text=overview_text,
        global_text=global_text,
        macro_text=macro_text,
        global_changes=[row.change_pct for row in global_rows],
    )

    yield status_event("status.market.research.start")

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
        for agent_id, agent_name, prepare, build in _DIMENSION_JOBS
    ]
    async for event in iter_queue_merged_events(queue, len(pumps)):
        yield event  # type: ignore[misc]
    await asyncio.gather(*pumps)

    yield status_event("status.market.research.news_factor")
    market_news = await fetch_market_news_snippets()
    news_text_factor = build_news_text_factor(market_news, subject=MARKET_NAME)

    yield status_event("status.market.research.summarize")
    if not with_debate:
        report = build_research_report(
            MARKET_SYMBOL,
            MARKET_NAME,
            dimensions,
            None,
            news_text_factor=news_text_factor,
            dimension_labels=_AGENT_LABELS,
        )
        yield status_event("status.market.research.report_done")
        yield {"type": "done", "result": report.model_dump(mode="json")}
        return

    situation = summarize_situation(dimensions)
    yield status_event("status.market.research.battle_start")

    enrichment = format_enrichment_block(ctx.global_text, ctx.macro_text)
    debate_context = f"{MARKET_NAME}\n用户关切：{query}\n作战情摘要：\n{situation}"
    if enrichment:
        debate_context += f"\n\n{enrichment}"
    debate: DebateResult | None = None
    async for event in iter_battle_events(
        client,
        bull_system=_BULL_SYSTEM,
        bear_system=_BEAR_SYSTEM,
        debate_context=debate_context,
        situation=situation,
        dimensions=dimensions,
        agent_labels=_AGENT_LABELS,
        bull_name="大盘看多",
        bear_name="大盘看空",
    ):
        if event.get("type") == "battle_result":
            debate = event["debate"]  # type: ignore[assignment]
            continue
        yield event

    report = build_research_report(
        MARKET_SYMBOL,
        MARKET_NAME,
        dimensions,
        debate,
        news_text_factor=news_text_factor,
        dimension_labels=_AGENT_LABELS,
    )

    if enable_master_commentary and mode_settings is not None:
        masters = master_ids or resolve_master_ids(mode_settings)
        commentary_context = build_market_context(report.summary)
        commentary: list[dict[str, Any]] = []
        async for mc_event in stream_master_commentary(
            client,
            subject=MARKET_NAME,
            context=commentary_context,
            settings=mode_settings,
            masters=masters,
        ):
            yield mc_event
            if mc_event.get("type") == "master_commentary" and isinstance(
                mc_event.get("commentary"), list
            ):
                commentary = mc_event["commentary"]
        report.master_commentary = [
            MasterCommentaryItem.model_validate(item) for item in commentary
        ]

    yield status_event("status.market.research.report_done")
    yield {"type": "done", "result": report.model_dump(mode="json")}
