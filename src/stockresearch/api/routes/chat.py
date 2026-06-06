"""Chat routes."""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.graph import Orchestrator
from stockresearch.agents.orchestrator.stream import run_chat_stream
from stockresearch.agents.output_style import output_style_scope
from stockresearch.api.deps import get_current_user
from stockresearch.api.llm_deps import resolve_llm_client
from stockresearch.api.routes.research import extract_reports_from_cards, persist_report
from stockresearch.core.exceptions import NotFoundError
from stockresearch.core.schemas import ChatRequest, ChatResponse, ResearchReportOut, StreamCheckpointOut
from stockresearch.db.models import User
from stockresearch.db.session import get_db
from stockresearch.services.stream_checkpoint import load_checkpoint

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_llm_api_key: str | None = Header(default=None, alias="X-LLM-Api-Key"),
    x_llm_base_url: str | None = Header(default=None, alias="X-LLM-Base-Url"),
    x_llm_model: str | None = Header(default=None, alias="X-LLM-Model"),
    x_llm_temperature: str | None = Header(default=None, alias="X-LLM-Temperature"),
    x_llm_use_mock: str | None = Header(default=None, alias="X-LLM-Use-Mock"),
) -> ChatResponse:
    llm = resolve_llm_client(
        payload.llm,
        x_llm_api_key=x_llm_api_key,
        x_llm_base_url=x_llm_base_url,
        x_llm_model=x_llm_model,
        x_llm_temperature=x_llm_temperature,
        x_llm_use_mock=x_llm_use_mock,
    )
    orchestrator = Orchestrator(db, llm=llm)
    with output_style_scope(tone=payload.output_tone, locale=payload.output_locale):
        return await orchestrator.run(
            user.id,
            payload.message,
            payload.session_id,
            payload.analysis_mode,
            enable_debate=payload.enable_debate,
            confirmed_symbol=payload.confirmed_symbol,
            confirmed_name=payload.confirmed_name,
            execution_preference=payload.execution_preference,
        )


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_llm_api_key: str | None = Header(default=None, alias="X-LLM-Api-Key"),
    x_llm_base_url: str | None = Header(default=None, alias="X-LLM-Base-Url"),
    x_llm_model: str | None = Header(default=None, alias="X-LLM-Model"),
    x_llm_temperature: str | None = Header(default=None, alias="X-LLM-Temperature"),
    x_llm_use_mock: str | None = Header(default=None, alias="X-LLM-Use-Mock"),
) -> StreamingResponse:
    llm = resolve_llm_client(
        payload.llm,
        x_llm_api_key=x_llm_api_key,
        x_llm_base_url=x_llm_base_url,
        x_llm_model=x_llm_model,
        x_llm_temperature=x_llm_temperature,
        x_llm_use_mock=x_llm_use_mock,
    )

    async def event_generator() -> AsyncIterator[str]:
        with output_style_scope(tone=payload.output_tone, locale=payload.output_locale):
            async for event in run_chat_stream(
                db,
                user.id,
                payload.message,
                payload.session_id,
                llm=llm,
                analysis_mode=payload.analysis_mode,
                enable_debate=payload.enable_debate,
                confirmed_symbol=payload.confirmed_symbol,
                confirmed_name=payload.confirmed_name,
                execution_preference=payload.execution_preference,
            ):
                if event.get("type") == "done":
                    response = event.get("response")
                    if isinstance(response, dict):
                        cards = response.get("cards", [])
                        if isinstance(cards, list):
                            for report in extract_reports_from_cards(cards):
                                persist_report(db, user.id, report)
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/checkpoint/{session_id}", response_model=StreamCheckpointOut)
def get_stream_checkpoint(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamCheckpointOut:
    checkpoint = load_checkpoint(db, user.id, session_id)
    if checkpoint is None:
        raise NotFoundError("暂无断点记录")
    return StreamCheckpointOut(session_id=session_id, checkpoint=checkpoint)
