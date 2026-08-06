"""Streaming sector/industry research — parallel dimensions + leader briefs + optional debate."""

import asyncio
from collections.abc import AsyncIterator
from typing import Literal

from sqlalchemy.orm import Session

from stockresearch.agents.industry.context import SectorResearchContext
from stockresearch.agents.industry.dimensions import (
    build_capital,
    build_policy,
    build_structure,
    build_technical,
    build_valuation,
    prepare_capital,
    prepare_policy,
    prepare_structure,
    prepare_technical,
    prepare_valuation,
)
from stockresearch.agents.industry.leaders import iter_leader_analysis_events
from stockresearch.agents.research.battle import iter_battle_events
from stockresearch.agents.research.budget import resolve_analysis_depth
from stockresearch.agents.research.debate import summarize_situation
from stockresearch.agents.research.report_builder import build_research_report
from stockresearch.agents.stream_typewriter import (
    iter_queue_merged_events,
    pump_dimension_llm_stream,
)
from stockresearch.agents.voice import DEBATE_VOICE, JUDGE_VOICE
from stockresearch.core.schemas import (
    DebateResult,
    DimensionResult,
    ModeSettingsOut,
    ResearchReportOut,
    SectorLeaderBrief,
)
from stockresearch.data.providers.sector import SectorDataProvider
from stockresearch.db.models import Holding, NewsItem
from stockresearch.i18n.status_events import status_event
from stockresearch.services.text_factor import build_news_text_factor, news_from_title
from stockresearch.utils.llm import LLMClient, get_llm_client

_BULL_SYSTEM = f"你是 A 股板块看多分析师。{DEBATE_VOICE}"
_BEAR_SYSTEM = f"你是 A 股板块看空分析师。{DEBATE_VOICE}"
_JUDGE_SYSTEM = f"""你是板块投研裁判。{JUDGE_VOICE} 只输出 JSON，禁止 markdown。
{{"bias":"偏多|偏空|中性","summary":"结论，2句内","reason":"为何如此判，2句内","divergence":"分歧大|分歧中等|分歧小","divergence_point":"分歧焦点，1句"}}"""

_AGENT_LABELS: dict[str, str] = {
    "policy": "政策舆情",
    "capital": "资金流向",
    "valuation": "估值景气",
    "technical": "技术走势",
    "structure": "结构持仓",
}

_DIMENSION_JOBS: list[tuple[str, str, object, object]] = [
    ("policy", "政策舆情", prepare_policy, build_policy),
    ("capital", "资金流向", prepare_capital, build_capital),
    ("valuation", "估值景气", prepare_valuation, build_valuation),
    ("technical", "技术走势", prepare_technical, build_technical),
    ("structure", "结构持仓", prepare_structure, build_structure),
]


async def _load_context(
    db: Session,
    user_id: int,
    sector: str,
    query: str,
    llm: LLMClient,
) -> SectorResearchContext:
    provider = SectorDataProvider()
    board, leaders = await asyncio.gather(
        provider.resolve_board(sector),
        provider.get_sector_leaders(sector, limit=3),
    )
    holdings = (
        db.query(Holding).filter(Holding.user_id == user_id, Holding.sector.contains(sector)).all()
    )
    holding_lines = [
        f"{h.name}({h.symbol}) 成本{h.float_cost_price:.2f} · {h.quantity}股" for h in holdings
    ]
    news_rows = db.query(NewsItem).order_by(NewsItem.published_at.desc()).limit(60).all()
    news_snippets = [
        n.title
        for n in news_rows
        if sector in n.title or sector in n.summary or sector in " ".join(n.entities or [])
    ][:8]
    return SectorResearchContext(
        sector=sector,
        query=query.strip() or sector,
        llm=llm,
        user_id=user_id,
        db=db,
        board=board,
        leaders=leaders,
        news_snippets=news_snippets,
        holding_lines=holding_lines,
    )


def _build_report(
    sector: str,
    dimensions: dict[str, DimensionResult],
    debate: DebateResult | None,
    leaders: list[SectorLeaderBrief],
    *,
    news_text_factor: str | None = None,
    analysis_depth: Literal["standard", "comprehensive", "deep"] = "standard",
) -> ResearchReportOut:
    board_code = "000000"
    if leaders:
        board_code = leaders[0].symbol or board_code

    summary_prefix = f"「{sector}」板块加权综合投研。"
    if leaders:
        summary_prefix += f" 龙头：{'、'.join(ld.name for ld in leaders[:2])}。"

    return build_research_report(
        board_code,
        sector,
        dimensions,
        debate,
        dimension_labels=_AGENT_LABELS,
        news_text_factor=news_text_factor,
        sector=sector,
        leaders=leaders,
        summary_prefix=summary_prefix,
        analysis_depth=analysis_depth,
    )


async def run_industry_research_stream(
    db: Session,
    user_id: int,
    sector: str,
    query: str,
    llm: LLMClient | None = None,
    *,
    with_debate: bool = False,
    mode_settings: ModeSettingsOut | None = None,
    analysis_depth: str | None = None,
) -> AsyncIterator[dict[str, object]]:
    client = llm or get_llm_client()
    depth = resolve_analysis_depth(
        explicit=analysis_depth,
        settings_depth=mode_settings.analysis_depth if mode_settings else None,
    )
    ctx = await _load_context(db, user_id, sector, query, client)

    yield status_event("status.industry.start", sector=sector)

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
    try:
        async for event in iter_queue_merged_events(queue, len(pumps)):
            yield event  # type: ignore[misc]
        await asyncio.gather(*pumps)
    finally:
        # Client disconnect: cancel pump tasks so LLM streams stop running on.
        for task in pumps:
            if not task.done():
                task.cancel()
        if pumps:
            await asyncio.gather(*pumps, return_exceptions=True)

    yield status_event("status.industry.leaders")
    leader_briefs: list[SectorLeaderBrief] = []
    async for event in iter_leader_analysis_events(ctx, ctx.leaders, limit=3):
        if event.get("type") == "leader_briefs":
            raw = event.get("leaders", [])
            if isinstance(raw, list):
                leader_briefs = [SectorLeaderBrief.model_validate(x) for x in raw]
        else:
            yield event

    debate: DebateResult | None = None
    if with_debate:
        situation = summarize_situation(dimensions)
        leader_note = "\n".join(f"- {ld.name}: {ld.brief}" for ld in leader_briefs)
        debate_context = f"板块：{sector}\n作战情报：\n{situation}\n龙头简评：\n{leader_note}"
        yield status_event("status.industry.battle_start")
        async for event in iter_battle_events(
            client,
            bull_system=_BULL_SYSTEM,
            bear_system=_BEAR_SYSTEM,
            debate_context=debate_context,
            situation=situation,
            dimensions=dimensions,
            agent_labels=_AGENT_LABELS,
            judge_system=_JUDGE_SYSTEM,
            judge_stream_id="sector_judge",
        ):
            if event.get("type") == "battle_result":
                debate = event["debate"]  # type: ignore[assignment]
                continue
            yield event

    news_snippets = [news_from_title(title) for title in ctx.news_snippets]
    news_text_factor = build_news_text_factor(news_snippets, subject=f"「{sector}」板块")
    report = _build_report(
        sector,
        dimensions,
        debate,
        leader_briefs,
        news_text_factor=news_text_factor,
        analysis_depth=depth,
    )

    yield status_event("status.industry.report_done")
    yield {"type": "done", "result": report.model_dump(mode="json")}
