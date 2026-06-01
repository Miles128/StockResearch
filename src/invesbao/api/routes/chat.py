"""Chat routes."""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from invesbao.agents.orchestrator.graph import Orchestrator
from invesbao.agents.orchestrator.stream import run_chat_stream
from invesbao.api.deps import get_current_user
from invesbao.core.schemas import ChatRequest, ChatResponse
from invesbao.db.models import User
from invesbao.db.session import get_db

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    orchestrator = Orchestrator(db)
    return await orchestrator.run(user.id, payload.message, payload.session_id)


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    async def event_generator() -> AsyncIterator[str]:
        async for event in run_chat_stream(
            db, user.id, payload.message, payload.session_id
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
