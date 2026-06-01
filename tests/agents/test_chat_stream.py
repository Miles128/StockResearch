"""Chat streaming orchestrator tests."""

import pytest
from sqlalchemy.orm import Session

from invesbao.agents.orchestrator.stream import run_chat_stream
from invesbao.db.models import User
from invesbao.services.auth import hash_password


@pytest.mark.asyncio
async def test_chat_stream_routes_research_with_live_events(db_session: Session) -> None:
    user = User(username="stream-test", password_hash=hash_password("password1"))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    events: list[dict[str, object]] = []
    async for event in run_chat_stream(db_session, user.id, "帮我分析一下600519"):
        events.append(event)

    types = [str(e.get("type")) for e in events]
    assert "status" in types
    assert "agent_start" in types
    assert types[-1] == "done"
    done = events[-1]
    response = done.get("response")
    assert isinstance(response, dict)
    assert response.get("reply")
