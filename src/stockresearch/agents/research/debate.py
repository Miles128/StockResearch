"""Bull vs Bear debate + judge agent (Research-Battle phase)."""

import asyncio
import re
from collections.abc import AsyncIterator, Callable
from typing import Any, Literal

from stockresearch.agents.stream_typewriter import (
    iter_llm_stream_events,
    iter_queue_merged_events,
    pump_llm_stream_events_to_queue,
)
from stockresearch.agents.structured_output import ResearchJudgeOut, VoteLabelOut
from stockresearch.agents.voice import (
    DEBATE_ROUNDS,
    DEBATE_VOICE,
    JUDGE_VOICE,
    bear_system,
    bull_system,
    research_judge_system,
)
from stockresearch.core.schemas import DebateResult, DebateRound, DimensionResult
from stockresearch.i18n.status_events import status_event
from stockresearch.utils.disclaimer import strip_disclaimer
from stockresearch.utils.llm import LLMClient

_BULL_SYSTEM = bull_system("A 股", "基于四维研究，说明最强看多逻辑。")

_BEAR_SYSTEM = bear_system("A 股", "指出主要下行风险与逻辑漏洞。")


def _dimension_summary(dimensions: dict[str, DimensionResult]) -> str:
    lines: list[str] = []
    for key, dim in dimensions.items():
        evidence_bits = [
            (e.snippet or "")[:60] for e in (dim.evidence or [])[:2] if (e.snippet or "").strip()
        ]
        evidence_part = f" 证据:{' | '.join(evidence_bits)}" if evidence_bits else ""
        lines.append(
            f"[{key}] 评分{dim.score}/10 置信{dim.confidence} "
            f"亮点:{'; '.join(dim.highlights)} 风险:{'; '.join(dim.risks)} "
            f"来源:{','.join(dim.data_sources)}{evidence_part}"
        )
    return "\n".join(lines)


def _trim_text(
    text: str,
    max_len: int | None,
    compact: Callable[[str, int], str] | None,
) -> str:
    cleaned = text.strip()
    if compact and max_len:
        return compact(cleaned, max_len)
    return cleaned


def _format_debate_utterance(raw: str) -> str:
    """Normalize debate text: ensure summary line and cap total length."""
    cleaned = strip_disclaimer(raw).strip()
    if not cleaned:
        return ""
    if "【摘要】" not in cleaned:
        if "\n" in cleaned:
            first, rest = cleaned.split("\n", 1)
            first, rest = first.strip(), rest.strip()
        else:
            parts = re.split(r"(?<=[。！？!?])\s*", cleaned, maxsplit=1)
            first = parts[0].strip()
            rest = parts[1].strip() if len(parts) > 1 else ""
        if rest:
            cleaned = f"【摘要】{first}\n【详述】{rest}"
        else:
            cleaned = f"【摘要】{first}"
    return cleaned


_ROUND_THEMES: dict[int, tuple[str, str]] = {
    1: (
        "陈述核心{side}逻辑，结合四维评分及亮点/风险中的可验证事实。",
        "陈述核心{side}逻辑，从四维薄弱项或主要风险切入。",
    ),
    2: (
        "回应对方上一轮论点，指出遗漏或偏差，并补充{side}侧论据。",
        "回应对方上一轮论点，说明其乐观假设的不足，并补充{side}侧风险论据。",
    ),
    3: (
        "归纳{side}立场，明确双方仍存分歧的关键问题。",
        "归纳{side}立场，明确双方仍存分歧的关键问题。",
    ),
}


def _round_theme(round_num: int, *, bullish: bool) -> str:
    themes = _ROUND_THEMES.get(round_num, _ROUND_THEMES[3])
    side = "看多" if bullish else "看空"
    template = themes[0] if bullish else themes[1]
    return template.format(side=side)


def _bull_prompt(context: str, round_num: int, transcript: list[str], side_label: str) -> str:
    theme = _round_theme(round_num, bullish=True)
    if round_num == 1:
        return f"{context}\n第1轮：{theme}"
    history = "\n".join(transcript)
    return f"{context}\n此前交锋：\n{history}\n第{round_num}轮：{theme}"


def _bear_prompt(
    context: str,
    round_num: int,
    transcript: list[str],
    bull_text: str,
    side_label: str,
) -> str:
    history = "\n".join(transcript) if transcript else ""
    prefix = f"此前：\n{history}\n" if history else ""
    theme = _round_theme(round_num, bullish=False)
    return (
        f"{context}\n第{round_num}轮{side_label}刚说：{bull_text}\n{prefix}第{round_num}轮：{theme}"
    )


def transcript_from_rounds(rounds: list[DebateRound]) -> str:
    lines: list[str] = []
    for item in rounds:
        lines.append(f"第{item.round}轮看多：{item.bull_argument}")
        lines.append(f"第{item.round}轮看空：{item.bear_rebuttal}")
    return "\n".join(lines)


def summarize_situation(dimensions: dict[str, DimensionResult]) -> str:
    return _dimension_summary(dimensions)


def dimension_vote(agent_key: str, label: str, dim: DimensionResult) -> tuple[str, str, str]:
    if dim.score >= 6.5:
        vote = "偏多"
    elif dim.score <= 4.5:
        vote = "偏空"
    else:
        vote = "中性"
    return agent_key, label, vote


def _parse_vote(raw: str) -> str:
    return VoteLabelOut.from_llm(raw).vote


async def iter_battle_vote_events(
    llm: LLMClient,
    dimensions: dict[str, DimensionResult],
    agent_labels: dict[str, str],
    debate_transcript: str,
    *,
    max_len: int | None = None,
    compact: Callable[[str, int], str] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    tally: dict[str, int] = {"偏多": 0, "偏空": 0, "中性": 0}
    yield status_event("status.debate.voting")

    for agent_id, dim in dimensions.items():
        _, label, vote = dimension_vote(agent_id, agent_labels.get(agent_id, agent_id), dim)
        tally[vote] += 1
        yield {
            "type": "vote",
            "agent_id": agent_id,
            "agent_name": label,
            "vote": vote,
        }

    for voter_id, voter_name, side_label in (
        ("bull", "看多派", "看多"),
        ("bear", "看空派", "看空"),
    ):
        yield {
            "type": "agent_start",
            "agent_id": voter_id,
            "agent_name": f"{voter_name}投票",
            "role": "vote",
        }
        raw = ""
        async for event in iter_llm_stream_events(
            stream_id=f"vote-{voter_id}",
            agent_id=voter_id,
            agent_name=f"{voter_name}投票",
            role="vote",
            llm=llm,
            system=f"你是{side_label}方。基于整场辩论，只输出一个词：偏多、偏空或中性。",
            user=debate_transcript,
        ):
            yield event
            if event.get("type") == "agent_done":
                raw = str(event.get("content", ""))
        vote = _parse_vote(_trim_text(raw, max_len, compact))
        tally[vote] += 1
        yield {
            "type": "vote",
            "agent_id": voter_id,
            "agent_name": voter_name,
            "vote": vote,
        }

    leading = max(tally, key=lambda key: tally[key])
    yield {
        "type": "vote_tally",
        "bullish": tally["偏多"],
        "bearish": tally["偏空"],
        "neutral": tally["中性"],
        "leading": leading,
        "message": f"投票：偏多 {tally['偏多']} · 偏空 {tally['偏空']} · 中性 {tally['中性']}",
    }


_RESEARCH_MANAGER_SYSTEM = f"""你是 Research Manager（投研负责人）。{JUDGE_VOICE}
阅读作战情报摘要、辩论记录与投票结果，只输出 JSON，禁止 markdown。
{{"investment_thesis":"投资要点2-3句","key_risk":"最大风险1-2句","debate_summary":"辩论核心1-2句","recommended_bias":"偏多|偏空|中性"}}
不要建议买卖。"""


async def iter_research_manager_events(
    llm: LLMClient,
    situation: str,
    debate_transcript: str,
    vote_summary: str,
    *,
    max_len: int | None = None,
    compact: Callable[[str, int], str] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    yield status_event("status.debate.manager")
    yield {
        "type": "agent_start",
        "agent_id": "research_manager",
        "agent_name": "Research Manager",
        "role": "manager",
    }
    user = f"作战情报摘要：\n{situation}\n\n辩论：\n{debate_transcript}\n\n{vote_summary}"
    thesis = ""
    async for event in iter_llm_stream_events(
        stream_id="research_manager",
        agent_id="research_manager",
        agent_name="Research Manager",
        role="manager",
        llm=llm,
        system=_RESEARCH_MANAGER_SYSTEM,
        user=user,
    ):
        yield event
        if event.get("type") == "agent_done":
            thesis = str(event.get("content", "")).strip()
    yield {"type": "manager", "content": thesis}


async def iter_triangular_debate_events(
    llm: LLMClient,
    context: str,
    *,
    rounds: int = DEBATE_ROUNDS,
    max_len: int | None = None,
    compact: Callable[[str, int], str] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    agents: list[tuple[str, str, str, str, str]] = [
        (
            "aggressive",
            "激进派",
            "aggressive",
            f"你是激进风控 Agent。{DEBATE_VOICE} 强调风险可控、可把握的机会。",
            "激进",
        ),
        (
            "neutral",
            "中性派",
            "neutral",
            f"你是中性风控 Agent。{DEBATE_VOICE} 平衡风险与收益，不偏不倚。",
            "中性",
        ),
        (
            "conservative",
            "审慎派",
            "conservative",
            f"你是审慎风控 Agent。{DEBATE_VOICE} 强调防守、回撤与集中度风险。",
            "审慎",
        ),
    ]
    transcript: list[str] = []
    for round_num in range(1, rounds + 1):
        yield status_event("status.debate.risk_round", round=round_num)
        round_texts: dict[str, str] = {}

        queue: asyncio.Queue[object] = asyncio.Queue()
        pumps: list[asyncio.Task[str]] = []
        history = "\n".join(transcript)
        for agent_id, agent_name, role, system, side_label in agents:
            if round_num == 1:
                task = f"结合持仓与告警数据，从{side_label}视角给出风险评估。"
            elif round_num == 2:
                task = "回应另外两派观点，指出其论证中的疏漏或偏差。"
            else:
                task = f"总结{side_label}立场，说明三方分歧焦点。"
            prompt = (
                f"{context}\n第{round_num}轮：{task}"
                if round_num == 1
                else f"{context}\n此前发言：\n{history}\n第{round_num}轮：{task}"
            )
            side_key = "neutral" if agent_id == "neutral" else agent_id
            stream_id = f"r{round_num}-{side_key}"
            yield {
                "type": "agent_start",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "role": role,
            }

            async def run_side(
                aid: str = agent_id,
                aname: str = agent_name,
                arole: str = role,
                asystem: str = system,
                sid: str = stream_id,
                user_prompt: str = prompt,
                q: asyncio.Queue[object] = queue,
            ) -> str:
                # 绑定默认参数：避免闭包延迟捕获轮次循环变量（B023）
                return await pump_llm_stream_events_to_queue(
                    q,
                    stream_id=sid,
                    agent_id=aid,
                    agent_name=aname,
                    role=arole,
                    llm=llm,
                    system=asystem,
                    user=user_prompt,
                )

            pumps.append(asyncio.create_task(run_side()))

        async for event in iter_queue_merged_events(queue, len(pumps)):
            if event.get("type") == "agent_done" and event.get("agent_id"):
                agent_id = str(event["agent_id"])
                content = str(event.get("content", ""))
                round_texts[agent_id] = content
                side_label = next(label for aid, _, _, _, label in agents if aid == agent_id)
                transcript.append(f"第{round_num}轮{side_label}：{content}")
            yield event
        await asyncio.gather(*pumps)

        yield {
            "type": "debate_round",
            "round": round_num,
            "aggressive": round_texts["aggressive"],
            "neutral_view": round_texts["neutral"],
            "conservative": round_texts["conservative"],
        }


def triangular_transcript(lines: list[str]) -> str:
    return "\n".join(lines)


async def run_multi_round_debate(
    llm: LLMClient,
    bull_system: str,
    bear_system: str,
    context: str,
    *,
    rounds: int = DEBATE_ROUNDS,
    max_len: int | None = None,
    compact: Callable[[str, int], str] | None = None,
    bull_side_label: str = "看多",
    bear_side_label: str = "看空",
) -> list[DebateRound]:
    transcript: list[str] = []
    result: list[DebateRound] = []
    for round_num in range(1, rounds + 1):
        bull_text = _format_debate_utterance(
            _trim_text(
                await llm.complete(
                    bull_system,
                    _bull_prompt(context, round_num, transcript, bull_side_label),
                ),
                max_len,
                compact,
            )
        )
        transcript.append(f"第{round_num}轮{bull_side_label}：{bull_text}")

        bear_text = _format_debate_utterance(
            _trim_text(
                await llm.complete(
                    bear_system,
                    _bear_prompt(context, round_num, transcript[:-1], bull_text, bull_side_label),
                ),
                max_len,
                compact,
            )
        )
        transcript.append(f"第{round_num}轮{bear_side_label}：{bear_text}")
        result.append(
            DebateRound(round=round_num, bull_argument=bull_text, bear_rebuttal=bear_text)
        )
    return result


async def iter_multi_round_debate_events(
    llm: LLMClient,
    bull_system: str,
    bear_system: str,
    context: str,
    *,
    rounds: int = DEBATE_ROUNDS,
    max_len: int | None = None,
    compact: Callable[[str, int], str] | None = None,
    bull_id: str = "bull",
    bear_id: str = "bear",
    bull_name: str = "看多派",
    bear_name: str = "看空派",
    bull_side_label: str = "看多",
    bear_side_label: str = "看空",
) -> AsyncIterator[dict[str, Any]]:
    transcript: list[str] = []
    for round_num in range(1, rounds + 1):
        yield status_event("status.debate.round", round=round_num)

        yield {
            "type": "agent_start",
            "agent_id": bull_id,
            "agent_name": bull_name,
            "role": "bull",
        }
        bull_text = ""
        async for event in iter_llm_stream_events(
            stream_id=f"r{round_num}-bull",
            agent_id=bull_id,
            agent_name=bull_name,
            role="bull",
            llm=llm,
            system=bull_system,
            user=_bull_prompt(context, round_num, transcript, bull_side_label),
        ):
            yield event
            if event.get("type") == "agent_done":
                bull_text = _format_debate_utterance(str(event.get("content", "")))
        transcript.append(f"第{round_num}轮{bull_side_label}：{bull_text}")

        yield {
            "type": "agent_start",
            "agent_id": bear_id,
            "agent_name": bear_name,
            "role": "bear",
        }
        bear_text = ""
        async for event in iter_llm_stream_events(
            stream_id=f"r{round_num}-bear",
            agent_id=bear_id,
            agent_name=bear_name,
            role="bear",
            llm=llm,
            system=bear_system,
            user=_bear_prompt(context, round_num, transcript[:-1], bull_text, bull_side_label),
        ):
            yield event
            if event.get("type") == "agent_done":
                bear_text = _format_debate_utterance(str(event.get("content", "")))
        transcript.append(f"第{round_num}轮{bear_side_label}：{bear_text}")

        yield {
            "type": "debate_round",
            "round": round_num,
            "bull": bull_text,
            "bear": bear_text,
        }


async def run_debate(
    symbol: str,
    name: str,
    dimensions: dict[str, DimensionResult],
    llm: LLMClient,
) -> DebateResult:
    context = _dimension_summary(dimensions)
    user_base = f"标的：{name}({symbol})\n四维研究：\n{context}"

    rounds = await run_multi_round_debate(
        llm,
        _BULL_SYSTEM,
        _BEAR_SYSTEM,
        user_base,
        bull_side_label="看多",
        bear_side_label="看空",
    )
    judge_user = f"{user_base}\n\n{transcript_from_rounds(rounds)}"
    # 与流式路径同一 JSON 裁判格式（voice.research_judge_system），
    # 同一解析器（ResearchJudgeOut.from_llm）——sync/stream 不再双格式漂移。
    judge_text = await llm.complete(research_judge_system(), judge_user)
    parsed = ResearchJudgeOut.from_llm(judge_text)

    bias = parsed.final_bias
    confidence = _infer_confidence(dimensions)

    return DebateResult(
        rounds=rounds,
        judge_verdict=judge_text.strip(),
        consensus=parsed.summary,
        core_divergence=f"{parsed.divergence}：{parsed.divergence_point}",
        final_bias=bias,
        confidence=confidence,
    )


def _infer_confidence(dimensions: dict[str, DimensionResult]) -> Literal["high", "medium", "low"]:
    levels = [d.confidence for d in dimensions.values()]
    if levels.count("high") >= 2:
        return "high"
    if "low" in levels:
        return "low"
    return "medium"
