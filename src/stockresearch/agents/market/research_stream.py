"""Streaming market-wide research — macro/industry/technical/sentiment."""

import asyncio
from collections.abc import AsyncIterator

from stockresearch.agents.market.context import MARKET_NAME, MARKET_SYMBOL, MarketResearchContext
from stockresearch.agents.market.dimensions import (
    build_industry,
    build_macro,
    build_sentiment,
    build_technical,
    format_overview_snapshot,
    prepare_industry,
    prepare_macro,
    prepare_sentiment,
    prepare_technical,
)
from stockresearch.agents.research.report_builder import build_research_report
from stockresearch.agents.stream_typewriter import (
    iter_queue_merged_events,
    pump_dimension_llm_stream,
)
from stockresearch.core.schemas import (
    DimensionResult,
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
    mode_settings: ModeSettingsOut | None = None,
) -> AsyncIterator[dict[str, object]]:
    """Market deep research across macro/industry/technical/sentiment."""
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
    report = build_research_report(
        MARKET_SYMBOL,
        MARKET_NAME,
        dimensions,
        news_text_factor=news_text_factor,
        dimension_labels=_AGENT_LABELS,
    )
    yield status_event("status.market.research.report_done")
    yield {"type": "done", "result": report.model_dump(mode="json")}
