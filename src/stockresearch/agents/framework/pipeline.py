"""Reusable building blocks for multi-agent streaming pipelines."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

from stockresearch.agents.research.debate import (
    iter_battle_vote_events,
    iter_multi_round_debate_events,
    iter_research_manager_events,
    summarize_situation,
    transcript_from_rounds,
)
from stockresearch.agents.stream_typewriter import (
    iter_llm_stream_events,
    iter_queue_merged_events,
    pump_dimension_llm_stream,
)
from stockresearch.agents.voice import DEBATE_ROUNDS
from stockresearch.core.schemas import DebateResult, DebateRound, DimensionResult
from stockresearch.utils.llm import LLMClient


@dataclass(frozen=True)
class DimensionJob:
    agent_id: str
    agent_name: str
    prepare: Callable[[object], Awaitable[tuple[str, str, object]]]
    build: Callable[[object, str], DimensionResult]


@dataclass(frozen=True)
class DebateConfig:
    bull_system: str
    bear_system: str
    judge_system: str
    parser: Callable[[str], object]
    agent_labels: dict[str, str]
    rounds: int = DEBATE_ROUNDS
    with_vote: bool = True
    with_manager: bool = True
    judge_stream_id: str = "judge"


async def stream_dimension_jobs(
    ctx: object,
    jobs: list[DimensionJob],
    dimensions: dict[str, DimensionResult],
) -> AsyncIterator[dict[str, object]]:
    """Yield agent_start + all dimension stream events; populate *dimensions*."""
    for job in jobs:
        yield {
            "type": "agent_start",
            "agent_id": job.agent_id,
            "agent_name": job.agent_name,
            "role": "analyst",
        }

    queue: asyncio.Queue[object] = asyncio.Queue()
    pumps = [
        asyncio.create_task(
            pump_dimension_llm_stream(
                queue,
                ctx=ctx,
                agent_id=job.agent_id,
                agent_name=job.agent_name,
                prepare=job.prepare,
                build=job.build,
                dimensions=dimensions,
            )
        )
        for job in jobs
    ]
    async for event in iter_queue_merged_events(queue, len(pumps)):
        yield event  # type: ignore[misc]
    await asyncio.gather(*pumps)


async def stream_debate_pipeline(
    llm: LLMClient,
    config: DebateConfig,
    debate_context: str,
    dimensions: dict[str, DimensionResult],
    out: list[DebateResult],
) -> AsyncIterator[dict[str, object]]:
    """Stream bull/bear debate, vote, manager, judge; append result to *out*."""
    debate_rounds: list[DebateRound] = []
    async for event in iter_multi_round_debate_events(
        llm,
        config.bull_system,
        config.bear_system,
        debate_context,
        rounds=config.rounds,
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
    if config.with_vote:
        async for event in iter_battle_vote_events(
            llm,
            dimensions,
            config.agent_labels,
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
    if config.with_manager:
        situation = summarize_situation(dimensions)
        async for event in iter_research_manager_events(
            llm,
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
        stream_id=config.judge_stream_id,
        agent_id="judge",
        agent_name="裁判",
        role="judge",
        llm=llm,
        system=config.judge_system,
        user=judge_user,
    ):
        yield event
        if event.get("type") == "agent_done":
            judge_raw = str(event.get("content", ""))

    parsed = config.parser(judge_raw)
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
    out.append(debate)

    yield {
        "type": "judge",
        "content": parsed.summary,
        "verdict": debate.final_bias,
        "summary": parsed.summary,
        "reason": parsed.reason,
        "divergence": parsed.divergence,
    }
