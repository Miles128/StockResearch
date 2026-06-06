"""Persist in-flight chat stream progress for resume hints (MVP checkpoint)."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from stockresearch.db.models import Conversation


def save_checkpoint(
    db: Session,
    user_id: int,
    session_id: str,
    payload: dict[str, object],
) -> None:
    conv = db.query(Conversation).filter(Conversation.session_id == session_id).first()
    if conv is None:
        conv = Conversation(user_id=user_id, session_id=session_id, messages=[])
        db.add(conv)
    checkpoint = dict(payload)
    checkpoint["updated_at"] = datetime.now(UTC).isoformat()
    conv.checkpoint = checkpoint
    db.commit()


def load_checkpoint(db: Session, user_id: int, session_id: str) -> dict[str, object] | None:
    conv = (
        db.query(Conversation)
        .filter(Conversation.session_id == session_id, Conversation.user_id == user_id)
        .first()
    )
    if conv is None or not conv.checkpoint:
        return None
    return dict(conv.checkpoint)


def clear_checkpoint(db: Session, user_id: int, session_id: str) -> None:
    conv = (
        db.query(Conversation)
        .filter(Conversation.session_id == session_id, Conversation.user_id == user_id)
        .first()
    )
    if conv is None:
        return
    conv.checkpoint = None
    db.commit()
