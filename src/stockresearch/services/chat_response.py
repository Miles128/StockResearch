"""Shared finalization and persistence for chat responses."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.balance_check import check_balance
from stockresearch.agents.output_style import get_custom_glossary, get_enable_glossary, get_reading_mode
from stockresearch.core.schemas import (
    CardPayload,
    ChatResponse,
    DebateResult,
    DimensionResult,
    ResearchReportOut,
)
from stockresearch.db.models import Conversation
from stockresearch.services.conversation_memory import MAX_STORED_MESSAGES
from stockresearch.services.follow_up import build_follow_up_questions
from stockresearch.services.glossary import mark_terms, merge_glossary
from stockresearch.services.neutral_guard import neutral_guard
from stockresearch.services.rotation_signal_guard import ensure_rotation_signals
from stockresearch.utils.disclaimer import strip_disclaimer
from stockresearch.utils.llm_usage import LlmUsageOut

logger = logging.getLogger(__name__)


def _mark_text_if_enabled(text: str) -> str:
    if not get_enable_glossary() or not text:
        return text
    glossary = merge_glossary(get_custom_glossary())
    return mark_terms(text, glossary=glossary)


def _finalize_text(text: str) -> str:
    """Apply compliance guard (PRD §六) then optional glossary term marking.

    Used for structured card text fields (highlights/risks/snippets/summary/
    viewpoints/debate arguments) so that forbidden position language (e.g.
    "目标价1800", "建议加仓") is scrubbed even when bypassing the chat reply
    path. Fact-layer numbers (score/confidence) are untouched because
    `neutral_guard` only does regex replacement on prose.
    """
    if not text:
        return text
    finalized = neutral_guard(text)
    return _mark_text_if_enabled(finalized)


def _finalize_str_list(items: list[str]) -> list[str]:
    return [_finalize_text(item) for item in items]


def _finalize_dimension(dim: DimensionResult) -> DimensionResult:
    """Apply compliance guard + glossary to all prose fields of a dimension.

    Covers highlights/risks/analysis and every evidence snippet (PRD §六
    applies to the whole UI, including evidence bars).
    """
    evidence = [
        ev.model_copy(update={"snippet": _finalize_text(ev.snippet)})
        for ev in dim.evidence
    ]
    return dim.model_copy(
        update={
            "highlights": _finalize_str_list(dim.highlights),
            "risks": _finalize_str_list(dim.risks),
            "analysis": _finalize_text(dim.analysis) if dim.analysis else dim.analysis,
            "evidence": evidence,
        }
    )


def _finalize_debate(debate: DebateResult) -> DebateResult:
    return debate.model_copy(
        update={
            "rounds": [
                rnd.model_copy(
                    update={
                        "bull_argument": _finalize_text(rnd.bull_argument),
                        "bear_rebuttal": _finalize_text(rnd.bear_rebuttal),
                    }
                )
                for rnd in debate.rounds
            ],
            "judge_verdict": _finalize_text(debate.judge_verdict),
            "consensus": _finalize_text(debate.consensus),
            "core_divergence": _finalize_text(debate.core_divergence),
            "manager_thesis": _finalize_text(debate.manager_thesis or "")
            if debate.manager_thesis
            else debate.manager_thesis,
        }
    )


def finalize_research_report(report: ResearchReportOut) -> ResearchReportOut:
    """Apply compliance guard (PRD §六) and glossary term marking to research card.

    Compliance guard always runs (PRD §六 is a hard constraint, not gated by
    glossary toggle); glossary marking is still gated by `enable_glossary`.
    """
    dimensions = {key: _finalize_dimension(dim) for key, dim in report.dimensions.items()}
    debate = _finalize_debate(report.debate) if report.debate else None
    master_commentary = [
        item.model_copy(
            update={
                "reasoning": _finalize_text(item.reasoning),
                "key_metric": _finalize_text(item.key_metric) if item.key_metric else item.key_metric,
            }
        )
        for item in report.master_commentary
    ]
    return report.model_copy(
        update={
            "summary": _finalize_text(report.summary),
            "brief_summary": _finalize_text(report.brief_summary) if report.brief_summary else report.brief_summary,
            "viewpoints": {key: _finalize_text(value) for key, value in report.viewpoints.items()},
            "text_factor_summary": _finalize_text(report.text_factor_summary or "")
            if report.text_factor_summary
            else report.text_factor_summary,
            "news_text_factor": _finalize_text(report.news_text_factor or "")
            if report.news_text_factor
            else report.news_text_factor,
            "dimensions": dimensions,
            "debate": debate,
            "master_commentary": master_commentary,
        }
    )


def finalize_cards(cards: list[dict[str, object]]) -> list[dict[str, object]]:
    """Apply shared output policy (compliance + glossary) to structured card payloads."""
    finalized: list[dict[str, object]] = []
    for card in cards:
        card_type = card.get("type")
        data = card.get("data")
        if card_type == "research" and isinstance(data, dict):
            try:
                report = ResearchReportOut.model_validate(data)
            except Exception:
                finalized.append(card)
                continue
            marked = finalize_research_report(report)
            finalized.append({"type": "research", "data": marked.model_dump(mode="json")})
            continue
        if card_type == "text" and isinstance(data, dict) and isinstance(data.get("content"), str):
            finalized.append(
                {
                    "type": "text",
                    "data": {"content": _finalize_text(str(data["content"]))},
                }
            )
            continue
        if card_type == "financial" and isinstance(data, dict):
            marked_data = dict(data)
            if isinstance(marked_data.get("summary"), str):
                marked_data["summary"] = _finalize_text(str(marked_data["summary"]))
            finalized.append({"type": "financial", "data": marked_data})
            continue
        finalized.append(card)
    return finalized


def finalize_chat_reply(reply: str, *, partial: bool = False) -> str:
    """Apply the single shared output policy for sync and streaming chat."""
    finalized = strip_disclaimer(reply)
    finalized = neutral_guard(finalized)
    finalized = check_balance(finalized)
    if get_reading_mode() == "friendly":
        finalized = ensure_rotation_signals(finalized)
    if get_enable_glossary():
        finalized = mark_terms(finalized)
    if partial:
        finalized = f"{finalized.rstrip()}\n\n（部分分析未完成）"
    return finalized


def assemble_chat_response(
    *,
    session_id: str,
    reply: str,
    cards: list[dict[str, object]],
    intent: str,
    partial: bool = False,
    llm_usage: LlmUsageOut | None = None,
) -> ChatResponse:
    """Build the final chat payload used by sync and streaming paths."""
    finalized = finalize_chat_reply(reply, partial=partial)
    finalized_cards = finalize_cards(cards)
    follow_ups = build_follow_up_questions(
        intent=intent,
        cards=finalized_cards,
        reading_mode=get_reading_mode(),
    )
    return ChatResponse(
        session_id=session_id,
        reply=finalized,
        cards=[CardPayload(type=c["type"], data=c["data"]) for c in finalized_cards],  # type: ignore[arg-type]
        intent=intent,
        partial=partial,
        follow_up_questions=follow_ups,
        llm_usage=llm_usage,
    )


def save_conversation(
    db: Session,
    user_id: int,
    session_id: str,
    user_message: str,
    assistant_reply: str,
) -> None:
    """Persist a bounded conversation history without breaking the response."""
    try:
        conversation = (
            db.query(Conversation).filter(Conversation.session_id == session_id).first()
        )
        if conversation is None:
            conversation = Conversation(
                user_id=user_id,
                session_id=session_id,
                messages=[],
            )
            db.add(conversation)
        messages = list(conversation.messages)
        messages.append({"role": "user", "content": user_message})
        messages.append({"role": "assistant", "content": assistant_reply})
        conversation.messages = messages[-MAX_STORED_MESSAGES:]
        db.commit()
    except Exception:
        logger.warning(
            "Failed to save conversation for session %s",
            session_id,
            exc_info=True,
        )
        db.rollback()
