"""Chat streaming orchestrator tests."""

import pytest
from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.stream import run_chat_stream
from stockresearch.db.models import User
from stockresearch.services.auth import hash_password


@pytest.mark.asyncio
async def test_chat_stream_stock_without_debate(db_session: Session) -> None:
    user = User(username="stream-choice", password_hash=hash_password("password1"))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    events: list[dict[str, object]] = []
    async for event in run_chat_stream(
        db_session,
        user.id,
        "帮我分析一下600519",
        enable_debate=False,
    ):
        events.append(event)

    assert events[0].get("type") == "status"
    status_msgs = [str(e.get("message", "")) for e in events if e.get("type") == "status"]
    assert any("多空辩论关" in m for m in status_msgs)
    types = [str(e.get("type")) for e in events]
    assert "debate_round" not in types


@pytest.mark.asyncio
async def test_chat_stream_returns_reply(db_session: Session) -> None:
    user = User(username="stream-test", password_hash=hash_password("password1"))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    events: list[dict[str, object]] = []
    async for event in run_chat_stream(
        db_session,
        user.id,
        "帮我分析一下600519",
        enable_debate=True,
    ):
        events.append(event)

    types = [str(e.get("type")) for e in events]
    assert "status" in types
    assert types[-1] == "done"
    done = events[-1]
    response = done.get("response")
    assert isinstance(response, dict)
    assert response.get("reply")
