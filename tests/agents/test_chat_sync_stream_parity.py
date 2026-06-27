"""Sync vs stream chat parity tests."""

import pytest
from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.graph import Orchestrator
from stockresearch.agents.orchestrator.stream import run_chat_stream
from stockresearch.agents.output_style import output_style_scope
from stockresearch.db.models import User


def _normalize_response(payload: dict[str, object]) -> dict[str, object]:
    return {
        "reply": str(payload.get("reply", "")).strip(),
        "intent": str(payload.get("intent", "")),
        "partial": bool(payload.get("partial", False)),
        "follow_up_questions": list(payload.get("follow_up_questions") or []),
        "card_types": [str(c.get("type")) for c in payload.get("cards", []) if isinstance(c, dict)],
    }


@pytest.mark.asyncio
async def test_sync_and_stream_match_for_react_chat(db_session: Session) -> None:
    user = User(username="parity-react", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    message = "你好，今天市场怎么样？"
    with output_style_scope(reading_mode="friendly", locale="zh"):
        sync = await Orchestrator(db_session).run(
            user.id,
            message,
            execution_preference="react",
            enable_debate=False,
        )
        events = [
            event
            async for event in run_chat_stream(
                db_session,
                user.id,
                message,
                execution_preference="react",
                enable_debate=False,
            )
        ]

    assert events[-1].get("type") == "done"
    stream_payload = events[-1].get("response")
    assert isinstance(stream_payload, dict)

    sync_payload = sync.model_dump(mode="json")
    assert _normalize_response(sync_payload) == _normalize_response(stream_payload)


@pytest.mark.asyncio
async def test_sync_and_stream_match_for_stock_research(db_session: Session) -> None:
    user = User(username="parity-research", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    message = "帮我分析一下600519"
    with output_style_scope(reading_mode="professional", locale="zh"):
        sync = await Orchestrator(db_session).run(
            user.id,
            message,
            enable_debate=False,
        )
        events = [
            event
            async for event in run_chat_stream(
                db_session,
                user.id,
                message,
                enable_debate=False,
            )
        ]

    stream_payload = events[-1].get("response")
    assert isinstance(stream_payload, dict)
    sync_payload = sync.model_dump(mode="json")

    assert sync_payload["intent"] == stream_payload["intent"]
    assert str(sync_payload["reply"]).strip() == str(stream_payload["reply"]).strip()
    assert sync_payload["partial"] == stream_payload["partial"]
    assert sync_payload.get("follow_up_questions") == stream_payload.get("follow_up_questions")

    sync_research = next(c for c in sync_payload["cards"] if c["type"] == "research")
    stream_research = next(c for c in stream_payload["cards"] if c["type"] == "research")
    assert sync_research["data"]["viewpoints"] == stream_research["data"]["viewpoints"]
    assert sync_research["data"]["data_gaps"] == stream_research["data"]["data_gaps"]


@pytest.mark.asyncio
async def test_stream_emits_single_final_done(db_session: Session) -> None:
    user = User(username="parity-done", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    events = [
        event
        async for event in run_chat_stream(
            db_session,
            user.id,
            "你好",
            execution_preference="react",
        )
    ]
    done_events = [event for event in events if event.get("type") == "done"]
    assert len(done_events) == 1
    assert done_events[-1] is events[-1]
