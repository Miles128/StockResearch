"""Chat streaming orchestrator tests."""

import pytest
from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.stream import run_chat_stream
from stockresearch.db.models import User
from stockresearch.services.auth import hash_password


@pytest.mark.asyncio
async def test_chat_stream_prompts_analysis_choice(db_session: Session) -> None:
    user = User(username="stream-choice", password_hash=hash_password("password1"))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    events: list[dict[str, object]] = []
    async for event in run_chat_stream(db_session, user.id, "帮我分析一下600519"):
        events.append(event)

    assert events[0].get("type") == "status"
    assert events[-1].get("type") == "analysis_choice"
    options = events[-1].get("options")
    assert isinstance(options, list) and len(options) == 2


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
        analysis_mode="complex",
    ):
        events.append(event)

    types = [str(e.get("type")) for e in events]
    assert "status" in types
    assert types[-1] == "done"
    done = events[-1]
    response = done.get("response")
    assert isinstance(response, dict)
    assert response.get("reply")
