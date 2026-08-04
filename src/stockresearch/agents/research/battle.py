"""辩论作战公共层：辩论 → 投票 → Research Manager → 裁判 → DebateResult。

research / market / industry 三条研究流水线共享同一条"辩论作战"流程，
此前各自重复实现约 90 行；现统一收敛到 ``iter_battle_events``。
"""

from collections.abc import AsyncIterator

from stockresearch.agents.research.debate import (
    iter_battle_vote_events,
    iter_multi_round_debate_events,
    iter_research_manager_events,
    transcript_from_rounds,
)
from stockresearch.agents.stream_typewriter import iter_llm_stream_events
from stockresearch.agents.structured_output import ResearchJudgeOut
from stockresearch.agents.voice import DEBATE_ROUNDS, JUDGE_VOICE
from stockresearch.core.schemas import DebateResult, DebateRound, DimensionResult
from stockresearch.utils.llm import LLMClient

JUDGE_RESEARCH_SYSTEM = f"""你是投研裁判。{JUDGE_VOICE} 只输出 JSON，禁止 markdown。
{{"bias":"偏多|偏空|中性","summary":"结论，2句内","reason":"为何如此判，2句内","divergence":"分歧大|分歧中等|分歧小","divergence_point":"分歧焦点，1句"}}"""


async def iter_battle_events(
    llm: LLMClient,
    *,
    bull_system: str,
    bear_system: str,
    debate_context: str,
    situation: str,
    dimensions: dict[str, DimensionResult],
    agent_labels: dict[str, str],
    judge_system: str = JUDGE_RESEARCH_SYSTEM,
    judge_stream_id: str = "judge",
    rounds: int = DEBATE_ROUNDS,
    bull_name: str = "看多派",
    bear_name: str = "看空派",
) -> AsyncIterator[dict[str, object]]:
    """Run the full battle flow, yielding all display events in order.

    Ends with a ``battle_result`` sentinel event carrying the assembled
    ``DebateResult`` and parsed judge output; callers intercept it instead
    of forwarding it downstream.
    """
    debate_rounds: list[DebateRound] = []
    async for event in iter_multi_round_debate_events(
        llm,
        bull_system,
        bear_system,
        debate_context,
        rounds=rounds,
        bull_name=bull_name,
        bear_name=bear_name,
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
    async for event in iter_battle_vote_events(llm, dimensions, agent_labels, debate_transcript):
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
        llm, situation, debate_transcript, vote_summary
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
        stream_id=judge_stream_id,
        agent_id="judge",
        agent_name="裁判",
        role="judge",
        llm=llm,
        system=judge_system,
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
    yield {"type": "battle_result", "debate": debate, "parsed": parsed}
