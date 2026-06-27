"""Shared finalization and persistence for chat responses."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.balance_check import check_balance
from stockresearch.agents.output_style import get_enable_glossary, get_reading_mode
from stockresearch.core.schemas import CardPayload, ChatResponse
from stockresearch.db.models import Conversation
from stockresearch.services.follow_up import build_follow_up_questions
from stockresearch.services.glossary import mark_terms
from stockresearch.services.neutral_guard import neutral_guard
from stockresearch.services.rotation_signal_guard import ensure_rotation_signals
from stockresearch.utils.disclaimer import strip_disclaimer
from stockresearch.utils.llm_usage import LlmUsageOut

logger = logging.getLogger(__name__)


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
    follow_ups = build_follow_up_questions(
        intent=intent,
        cards=cards,
        reading_mode=get_reading_mode(),
    )
    return ChatResponse(
        session_id=session_id,
        reply=finalized,
        cards=[CardPayload(type=c["type"], data=c["data"]) for c in cards],  # type: ignore[arg-type]
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
        conversation.messages = messages[-20:]
        db.commit()
    except Exception:
        logger.warning(
            "Failed to save conversation for session %s",
            session_id,
            exc_info=True,
        )
        db.rollback()
