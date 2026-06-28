"""Shared finalization and persistence for chat responses."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.balance_check import check_balance
from stockresearch.agents.output_style import get_enable_glossary, get_reading_mode
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
from stockresearch.services.glossary import mark_terms
from stockresearch.services.neutral_guard import neutral_guard
from stockresearch.services.rotation_signal_guard import ensure_rotation_signals
from stockresearch.utils.disclaimer import strip_disclaimer
from stockresearch.utils.llm_usage import LlmUsageOut

logger = logging.getLogger(__name__)


def _mark_text_if_enabled(text: str) -> str:
    if not get_enable_glossary() or not text:
        return text
    return mark_terms(text)


def _mark_str_list(items: list[str]) -> list[str]:
    return [_mark_text_if_enabled(item) for item in items]


def _mark_dimension(dim: DimensionResult) -> DimensionResult:
    return dim.model_copy(
        update={
            "highlights": _mark_str_list(dim.highlights),
            "risks": _mark_str_list(dim.risks),
        }
    )


def _mark_debate(debate: DebateResult) -> DebateResult:
    return debate.model_copy(
        update={
            "rounds": [
                rnd.model_copy(
                    update={
                        "bull_argument": _mark_text_if_enabled(rnd.bull_argument),
                        "bear_rebuttal": _mark_text_if_enabled(rnd.bear_rebuttal),
                    }
                )
                for rnd in debate.rounds
            ],
            "judge_verdict": _mark_text_if_enabled(debate.judge_verdict),
            "consensus": _mark_text_if_enabled(debate.consensus),
            "core_divergence": _mark_text_if_enabled(debate.core_divergence),
            "manager_thesis": _mark_text_if_enabled(debate.manager_thesis or "")
            if debate.manager_thesis
            else debate.manager_thesis,
        }
    )


def finalize_research_report(report: ResearchReportOut) -> ResearchReportOut:
    """Mark glossary terms in research card text fields."""
    if not get_enable_glossary():
        return report
    dimensions = {key: _mark_dimension(dim) for key, dim in report.dimensions.items()}
    debate = _mark_debate(report.debate) if report.debate else None
    master_commentary = [
        item.model_copy(update={"reasoning": _mark_text_if_enabled(item.reasoning)})
        for item in report.master_commentary
    ]
    return report.model_copy(
        update={
            "summary": _mark_text_if_enabled(report.summary),
            "viewpoints": {key: _mark_text_if_enabled(value) for key, value in report.viewpoints.items()},
            "text_factor_summary": _mark_text_if_enabled(report.text_factor_summary or "")
            if report.text_factor_summary
            else report.text_factor_summary,
            "news_text_factor": _mark_text_if_enabled(report.news_text_factor or "")
            if report.news_text_factor
            else report.news_text_factor,
            "dimensions": dimensions,
            "debate": debate,
            "master_commentary": master_commentary,
        }
    )


def finalize_cards(cards: list[dict[str, object]]) -> list[dict[str, object]]:
    """Apply shared output policy to structured card payloads."""
    finalized: list[dict[str, object]] = []
    for card in cards:
        if card.get("type") != "research" or not isinstance(card.get("data"), dict):
            finalized.append(card)
            continue
        try:
            report = ResearchReportOut.model_validate(card["data"])
        except Exception:
            finalized.append(card)
            continue
        marked = finalize_research_report(report)
        finalized.append({"type": "research", "data": marked.model_dump(mode="json")})
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
