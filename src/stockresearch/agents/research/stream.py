"""Streaming multi-agent research — parallel dimensions + debate + report."""

import asyncio
import logging
from collections.abc import AsyncIterator
from stockresearch.agents.research.report_builder import build_research_report
from stockresearch.agents.research.debate import (
    iter_battle_vote_events,
    iter_multi_round_debate_events,
    iter_research_manager_events,
    summarize_situation,
    transcript_from_rounds,
)
from stockresearch.agents.research.context import ResearchContext
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
from stockresearch.agents.stream_typewriter import (
    iter_llm_stream_events,
    iter_queue_merged_events,
    pump_dimension_llm_stream,
)
from stockresearch.agents.structured_output import ResearchJudgeOut
from stockresearch.agents.voice import DEBATE_ROUNDS, DEBATE_VOICE, JUDGE_VOICE
from stockresearch.core.schemas import DebateResult, DebateRound, DimensionResult, ResearchReportOut
from stockresearch.services.text_factor import build_news_text_factor, fetch_symbol_news_snippets
from stockresearch.i18n.status_events import status_event
from stockresearch.utils.llm import LLMClient, get_llm_client
from stockresearch.utils.symbols import resolve_name

logger = logging.getLogger(__name__)

_BULL_SYSTEM = f"你是看多 Agent。{DEBATE_VOICE}"
_BEAR_SYSTEM = f"你是看空 Agent。{DEBATE_VOICE}"
_JUDGE_RESEARCH_SYSTEM = f"""你是投研裁判。{JUDGE_VOICE} 只输出 JSON，禁止 markdown。
{{"bias":"偏多|偏空|中性","summary":"结论，2句内","reason":"为何如此判，2句内","divergence":"分歧大|分歧中等|分歧小","divergence_point":"分歧焦点，1句"}}"""

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


def _parse_research_judge(raw: str) -> ResearchJudgeOut:
    return ResearchJudgeOut.from_llm(raw)


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
) -> ResearchReportOut:
    return build_research_report(
        symbol,
        name,
        dimensions,
        debate,
        dimension_labels=dimension_labels or _AGENT_LABELS,
        news_text_factor=news_text_factor,
    )


async def run_research_stream(
    symbol: str,
    llm: LLMClient | None = None,
    *,
    with_debate: bool = True,
) -> AsyncIterator[dict[str, object]]:
    client = llm or get_llm_client()
    ctx = ResearchContext(symbol=symbol, llm=client)
    name = resolve_name(symbol)

    yield status_event("status.research.start", name=name, symbol=symbol)

    for agent_id, agent_name, _, _ in _DIMENSION_STREAM_JOBS:
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
        for agent_id, agent_name, prepare, build in _DIMENSION_STREAM_JOBS
    ]
    async for event in iter_queue_merged_events(queue, len(pumps)):
        yield event  # type: ignore[misc]
    await asyncio.gather(*pumps)

    yield status_event("status.research.news_factor")
    news_snippets = await fetch_symbol_news_snippets(symbol, name)
    news_text_factor = build_news_text_factor(news_snippets, subject=f"{name}({symbol})")

    yield status_event("status.research.summarize")
    if not with_debate:
        report = _build_report(symbol, name, dimensions, None, news_text_factor=news_text_factor)
        yield status_event("status.research.report_done")
        yield {"type": "done", "result": report.model_dump(mode="json")}
        return

    situation = summarize_situation(dimensions)
    yield status_event("status.research.battle_start")

    debate_context = f"{name}({symbol})\n作战情摘要：\n{situation}"
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
    async for event in iter_battle_vote_events(
        client,
        dimensions,
        _AGENT_LABELS,
        debate_transcript,
    ):
        yield event
        if event.get("type") == "vote_tally":
            vote_tally = {
                "偏多": int(event.get("bullish", 0)),
                "偏空": int(event.get("bearish", 0)),
                "中性": int(event.get("neutral", 0)),
            }
            vote_summary = str(event.get("message", ""))

    manager_thesis = ""
    async for event in iter_research_manager_events(
        client,
        situation,
        debate_transcript,
        vote_summary,
    ):
        yield event
        if event.get("type") == "manager":
            manager_thesis = str(event.get("content", ""))

    yield {
        "type": "agent_start",
        "agent_id": "judge",
        "agent_name": "裁判",
        "role": "judge",
    }
    judge_user = f"{debate_transcript}\n\n{vote_summary}\n\nResearch Manager：\n{manager_thesis}"
    judge_raw = ""
    async for event in iter_llm_stream_events(
        stream_id="judge",
        agent_id="judge",
        agent_name="裁判",
        role="judge",
        llm=client,
        system=_JUDGE_RESEARCH_SYSTEM,
        user=judge_user,
    ):
        yield event
        if event.get("type") == "agent_done":
            judge_raw = str(event.get("content", ""))
    parsed = _parse_research_judge(judge_raw)
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

    report = _build_report(symbol, name, dimensions, debate, news_text_factor=news_text_factor)
    yield status_event("status.research.report_done")
    yield {"type": "done", "result": report.model_dump(mode="json")}
