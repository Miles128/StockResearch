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
from stockresearch.agents.research.debate import (
    iter_battle_vote_events,
    iter_multi_round_debate_events,
    iter_research_manager_events,
    summarize_situation,
    transcript_from_rounds,
)
from stockresearch.agents.stream_typewriter import iter_llm_stream_events, iter_queue_merged_events, pump_dimension_llm_stream
from stockresearch.agents.structured_output import ResearchJudgeOut
from stockresearch.agents.voice import DEBATE_ROUNDS, DEBATE_VOICE, JUDGE_VOICE
from stockresearch.core.constants import CONFIDENCE_HIGH, CONFIDENCE_LOW
from stockresearch.core.schemas import DebateResult, DebateRound, DimensionResult, ResearchReportOut, SectorLeaderBrief
from stockresearch.data.providers.sector import SectorDataProvider
from stockresearch.db.models import Holding, NewsItem
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


def _as_confidence(value: str) -> Literal["high", "medium", "low"]:
    if value == CONFIDENCE_HIGH:
        return "high"
    if value == CONFIDENCE_LOW:
        return "low"
    return "medium"


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
        db.query(Holding)
        .filter(Holding.user_id == user_id, Holding.sector.contains(sector))
        .all()
    )
    holding_lines = [
        f"{h.name}({h.symbol}) 成本{h.cost_price:.2f} · {h.quantity}股"
        for h in holdings
    ]
    news_rows = (
        db.query(NewsItem)
        .order_by(NewsItem.published_at.desc())
        .limit(60)
        .all()
    )
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
) -> ResearchReportOut:
    scores = [d.score for d in dimensions.values()]
    composite = round(sum(scores) / len(scores), 1)
    confidences = [d.confidence for d in dimensions.values()]
    if confidences.count("high") >= 2:
        composite_confidence: Literal["high", "medium", "low"] = "high"
    elif "low" in confidences:
        composite_confidence = "low"
    else:
        composite_confidence = "medium"

    if composite >= 6.5:
        bias: Literal["bullish", "bearish", "neutral"] = "bullish"
    elif composite <= 4.5:
        bias = "bearish"
    else:
        bias = "neutral"

    board_code = "000000"
    if leaders:
        board_code = leaders[0].symbol or board_code

    summary = (
        f"「{sector}」板块综合 {composite}/10，"
        f"倾向{'偏多' if bias == 'bullish' else '偏空' if bias == 'bearish' else '中性'}。"
    )
    if leaders:
        summary += f" 龙头：{'、'.join(ld.name for ld in leaders[:2])}。"
    if debate:
        bias_label = (
            "偏多" if debate.final_bias == "bullish"
            else "偏空" if debate.final_bias == "bearish"
            else "中性"
        )
        summary += f" 裁判{bias_label}：{debate.consensus}"

    return ResearchReportOut(
        symbol=board_code,
        name=sector,
        sector=sector,
        dimensions=dimensions,
        composite_score=composite,
        composite_confidence=composite_confidence,
        bias=bias,
        summary=summary,
        debate=debate,
        leaders=leaders,
    )


async def run_industry_research_stream(
    db: Session,
    user_id: int,
    sector: str,
    query: str,
    llm: LLMClient | None = None,
    *,
    with_debate: bool = False,
) -> AsyncIterator[dict[str, object]]:
    client = llm or get_llm_client()
    ctx = await _load_context(db, user_id, sector, query, client)

    yield {"type": "status", "message": f"启动「{sector}」板块五维深度研究…"}

    for agent_id, agent_name, _, _ in _DIMENSION_JOBS:
        yield {
            "type": "agent_start",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "role": "analyst",
        }

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

    yield {"type": "status", "message": "五维完成，分析板块龙头…"}
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
        debate_context = f"板块：{sector}\n作战情：\n{situation}\n龙头简评：\n{leader_note}"
        yield {"type": "status", "message": "进入板块多空 Battle…"}
        debate_rounds: list[DebateRound] = []
        async for event in iter_multi_round_debate_events(
            client,
            _BULL_SYSTEM,
            _BEAR_SYSTEM,
            debate_context,
            rounds=DEBATE_ROUNDS,
        ):
            yield event
            if event.get("type") == "debate_round":
                round_num = event.get("round")
                if isinstance(round_num, int):
                    debate_rounds.append(
                        DebateRound(
                            round=round_num,
                            bull_argument=str(event.get("bull", "")),
                            bear_rebuttal=str(event.get("bear", "")),
                        )
                    )
        debate_transcript = transcript_from_rounds(debate_rounds)
        vote_tally: dict[str, int] | None = None
        vote_summary = ""
        async for event in iter_battle_vote_events(client, dimensions, _AGENT_LABELS, debate_transcript):
            yield event
            if event.get("type") == "vote_tally":
                vote_tally = {
                    "偏多": int(event.get("bullish", 0)),
                    "偏空": int(event.get("bearish", 0)),
                    "中性": int(event.get("neutral", 0)),
                }
                vote_summary = str(event.get("message", ""))
        manager_thesis = ""
        async for event in iter_research_manager_events(client, situation, debate_transcript, vote_summary):
            yield event
            if event.get("type") == "manager":
                manager_thesis = str(event.get("content", ""))
        judge_user = f"{debate_transcript}\n\n{vote_summary}\n\nResearch Manager：\n{manager_thesis}"
        judge_raw = ""
        async for event in iter_llm_stream_events(
            stream_id="sector_judge",
            agent_id="judge",
            agent_name="裁判",
            role="judge",
            llm=client,
            system=_JUDGE_SYSTEM,
            user=judge_user,
        ):
            yield event
            if event.get("type") == "agent_done":
                judge_raw = str(event.get("content", ""))
        parsed = ResearchJudgeOut.from_llm(judge_raw)
        debate = DebateResult(
            rounds=debate_rounds,
            judge_verdict=f"{parsed.summary} {parsed.reason}",
            consensus=parsed.summary,
            core_divergence=f"{parsed.divergence}：{parsed.divergence_point}",
            final_bias=parsed.final_bias,
            confidence="medium",
            vote_tally=vote_tally,
            manager_thesis=manager_thesis or None,
        )
        yield {
            "type": "judge",
            "content": parsed.summary,
            "verdict": debate.final_bias,
            "summary": parsed.summary,
            "reason": parsed.reason,
            "divergence": parsed.divergence,
        }

    report = _build_report(sector, dimensions, debate, leader_briefs)
    yield {"type": "status", "message": "板块投研报告已生成"}
    yield {"type": "done", "result": report.model_dump(mode="json")}
