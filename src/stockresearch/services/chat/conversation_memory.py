"""Conversation history load, persistence helpers, and compression."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from stockresearch.db.models import Conversation

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from stockresearch.utils.llm import LLMClient

logger = logging.getLogger(__name__)

MEMORY_CHAR_LIMIT = 10_000
MAX_STORED_MESSAGES = 40
KEEP_RECENT_MESSAGES = 8


def _message_chars(messages: list[dict[str, str]]) -> int:
    return sum(len(str(m.get("content", ""))) for m in messages)


def load_conversation_messages(db: Session, user_id: int, session_id: str) -> list[dict[str, str]]:
    """Return prior turns for a session (empty if new)."""
    conversation = (
        db.query(Conversation)
        .filter(Conversation.session_id == session_id, Conversation.user_id == user_id)
        .first()
    )
    if conversation is None or not conversation.messages:
        return []
    out: list[dict[str, str]] = []
    for item in conversation.messages:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", ""))
        content = str(item.get("content", "")).strip()
        if role in ("user", "assistant") and content:
            out.append({"role": role, "content": content})
    return out


async def compress_messages_if_needed(
    llm: LLMClient,
    messages: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Summarize older turns when total length exceeds MEMORY_CHAR_LIMIT."""
    if _message_chars(messages) <= MEMORY_CHAR_LIMIT:
        return messages
    if len(messages) <= 1:
        return messages

    keep = min(KEEP_RECENT_MESSAGES, len(messages) - 1)
    if keep < 1:
        return messages

    older = messages[:-keep]
    recent = messages[-keep:]
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in older)
    system = (
        "你是会话摘要助手。将以下对话历史压缩为简洁中文摘要，"
        "保留：讨论过的标的、用户偏好、已给出的关键结论与未决问题。"
        "不要添加新事实。200～400 字。"
    )
    try:
        summary = await llm.complete(system, transcript[:12000])
    except Exception:
        logger.warning("Conversation compression failed; truncating older turns", exc_info=True)
        summary = transcript[:800] + "…（较早对话已截断）"

    compressed = [{"role": "assistant", "content": f"【会话摘要】\n{summary.strip()}"}]
    return compressed + recent


async def prepare_chat_history(
    db: Session,
    user_id: int,
    session_id: str,
    llm: LLMClient,
) -> list[dict[str, str]]:
    """Load session history and compress when over the char budget."""
    messages = load_conversation_messages(db, user_id, session_id)
    if not messages:
        return []
    messages = await compress_messages_if_needed(llm, messages)
    return messages[-MAX_STORED_MESSAGES:]
