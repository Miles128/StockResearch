"""Chat routes."""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.graph import Orchestrator
from stockresearch.agents.orchestrator.stream import run_chat_stream
from stockresearch.agents.output_style import output_style_scope
from stockresearch.api.deps import get_current_user
from stockresearch.api.llm_deps import resolve_llm_client
from stockresearch.api.rate_limit import limiter
from stockresearch.api.routes.research import (
    attach_report_ids_to_cards,
    extract_reports_from_cards,
    persist_report,
)
from stockresearch.core.exceptions import NotFoundError
from stockresearch.core.schemas import ChatRequest, ChatResponse, StreamCheckpointOut
from stockresearch.db.models import User
from stockresearch.db.session import get_db
from stockresearch.services.stream_checkpoint import load_checkpoint
from stockresearch.services.user_preferences import get_mode_settings

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
@limiter.limit("10/minute")
async def chat(
    request: Request,
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
    mode_settings = get_mode_settings(db, user.id)
    glossary_on = (
        payload.enable_glossary
        if payload.enable_glossary is not None
        else mode_settings.enable_glossary
    )
    orchestrator = Orchestrator(db, llm=llm)
    with output_style_scope(
        reading_mode=payload.reading_mode,
        locale=payload.output_locale,
        enable_glossary=glossary_on,
        custom_glossary=mode_settings.custom_glossary,
    ):
        return await orchestrator.run(
            user.id,
            payload.message,
            payload.session_id,
            enable_debate=payload.enable_debate,
            enable_master_commentary=payload.enable_master_commentary,
            user_context=payload.user_context,
            mode_settings=mode_settings,
            confirmed_symbol=payload.confirmed_symbol,
            confirmed_name=payload.confirmed_name,
            execution_preference=payload.execution_preference,
        )


@router.post("/stream")
@limiter.limit("10/minute")
async def chat_stream(
    request: Request,
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
    mode_settings = get_mode_settings(db, user.id)
    glossary_on = (
        payload.enable_glossary
        if payload.enable_glossary is not None
        else mode_settings.enable_glossary
    )

    async def event_generator() -> AsyncIterator[str]:
        import asyncio

        async def _stream_with_keepalive():
            with output_style_scope(
                reading_mode=payload.reading_mode,
                locale=payload.output_locale,
                enable_glossary=glossary_on,
                custom_glossary=mode_settings.custom_glossary,
            ):
                async for event in run_chat_stream(
                    db,
                    user.id,
                    payload.message,
                    payload.session_id,
                    llm=llm,
                    enable_debate=payload.enable_debate,
                    enable_master_commentary=payload.enable_master_commentary,
                    user_context=payload.user_context,
                    mode_settings=mode_settings,
                    confirmed_symbol=payload.confirmed_symbol,
                    confirmed_name=payload.confirmed_name,
                    execution_preference=payload.execution_preference,
                ):
                    yield event

        stream = _stream_with_keepalive()
        next_deadline = asyncio.get_running_loop().time() + 15

        async for event in stream:
            if event.get("type") == "done":
                response = event.get("response")
                if isinstance(response, dict):
                    cards = response.get("cards", [])
                    if isinstance(cards, list):
                        id_by_symbol: dict[str, int] = {}
                        for report in extract_reports_from_cards(cards):
                            row = persist_report(db, user.id, report)
                            id_by_symbol[report.symbol] = row.id
                        if id_by_symbol:
                            stamped = attach_report_ids_to_cards(cards, id_by_symbol)
                            response = {**response, "cards": stamped}
                            event = {**event, "response": response}
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
            now = asyncio.get_running_loop().time()
            if now >= next_deadline:
                yield ": keep-alive\n\n"
                next_deadline = now + 15

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
