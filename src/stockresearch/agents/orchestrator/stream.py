"""Streaming chat orchestrator — real-time progress + ReAct/Debate/PlanExecute."""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator

import httpx
from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.chat_execute import execute_chat_turn
from stockresearch.core.exceptions import LLMConfigError
from stockresearch.core.schemas import ChatUserContext, ModeSettingsOut
from stockresearch.db.models import Holding
from stockresearch.i18n.status_events import status_event
from stockresearch.services.chat_scope import PreparedChatTurn, prepare_chat_turn
from stockresearch.services.chat_response import assemble_chat_response, save_conversation
from stockresearch.services.conversation_memory import prepare_chat_history
from stockresearch.services.stream_checkpoint import clear_checkpoint, save_checkpoint
from stockresearch.services.user_preferences import get_mode_settings
from stockresearch.utils.llm import LLMClient, get_llm_client
from stockresearch.utils.llm_usage import get_usage, reset_usage, usage_to_out

logger = logging.getLogger(__name__)


def _llm_model_name(client: LLMClient) -> str:
    return str(getattr(client, "_model", "") or "")


def _resolve_master_on(
    request_flag: bool | None,
    settings: ModeSettingsOut,
) -> bool:
    if request_flag is not None:
        return bool(request_flag)
    return bool(settings.enable_master_commentary)


async def run_chat_stream(
    db: Session,
    user_id: int,
    message: str,
    session_id: str | None = None,
    llm: LLMClient | None = None,
    enable_debate: bool | None = None,
    enable_master_commentary: bool | None = None,
    user_context: ChatUserContext | None = None,
    mode_settings: ModeSettingsOut | None = None,
    confirmed_symbol: str | None = None,
    confirmed_name: str | None = None,
    execution_preference: str | None = None,
) -> AsyncIterator[dict[str, object]]:
    """Yield SSE events with real-time progress updates."""
    sid = session_id or str(uuid.uuid4())
    client = llm or get_llm_client()
    reset_usage(model=_llm_model_name(client))
    holdings = db.query(Holding).filter(Holding.user_id == user_id).all()
    settings = mode_settings or get_mode_settings(db, user_id)
    master_on = _resolve_master_on(enable_master_commentary, settings)
    prepared = await prepare_chat_turn(
        mode_settings=settings,
        holdings=holdings,
        message=message,
        user_context=user_context,
        llm=client,
        confirmed_symbol=confirmed_symbol,
        confirmed_name=confirmed_name,
    )
    history = await prepare_chat_history(db, user_id, sid, client)

    yield status_event("status.understanding")

    debate_on = (
        settings.enable_debate if enable_debate is None else bool(enable_debate)
    )
    cards: list[dict[str, object]] = []
    reply = ""
    partial = False
    intent = "chat"

    try:
        async for event in _run_chat_stream_body(
            db=db,
            user_id=user_id,
            message=prepared.message,
            sid=sid,
            client=client,
            holdings=prepared.holdings,
            debate_on=debate_on,
            master_on=master_on,
            prepared=prepared,
            history=history,
            confirmed_symbol=confirmed_symbol,
            confirmed_name=confirmed_name,
            execution_preference=execution_preference,
            mode_settings=settings,
            user_context=user_context,
        ):
            if isinstance(event, dict) and event.get("type") == "done" and "response" in event:
                response = event["response"]
                if isinstance(response, dict):
                    reply = str(response.get("reply", ""))
                    cards = list(response.get("cards", []))
                    intent = str(response.get("intent", intent))
                    partial = bool(response.get("partial", False))
            if not (
                isinstance(event, dict)
                and event.get("type") == "done"
                and "response" in event
            ):
                yield event
    except LLMConfigError as exc:
        logger.warning("LLM config error in chat stream: %s", exc)
        yield {
            "type": "error",
            "code": "llm_not_configured",
            "message": str(exc),
        }
        return

    response = assemble_chat_response(
        session_id=sid,
        reply=reply,
        cards=cards,
        intent=intent,
        partial=partial,
        llm_usage=usage_to_out(get_usage()),
    )
    clear_checkpoint(db, user_id, sid)

    save_conversation(db, user_id, sid, prepared.message, response.reply)

    yield {"type": "done", "response": response.model_dump(mode="json")}


async def _run_chat_stream_body(
    *,
    db: Session,
    user_id: int,
    message: str,
    sid: str,
    client: LLMClient,
    holdings: list[Holding],
    debate_on: bool,
    master_on: bool,
    prepared: PreparedChatTurn,
    history: list[dict[str, str]],
    confirmed_symbol: str | None,
    confirmed_name: str | None,
    execution_preference: str | None,
    mode_settings: ModeSettingsOut,
    user_context: ChatUserContext | None,
) -> AsyncIterator[dict[str, object]]:
    """Skill-first ReAct stream — shared execute path with sync /chat."""
    cards: list[dict[str, object]] = []
    reply = ""
    intent = "chat"
    partial = False
    progress_queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue()

    async def on_progress(hint: dict[str, object]) -> None:
        await progress_queue.put(hint)

    async def _run_turn() -> None:
        nonlocal cards, reply, intent, partial
        try:
            result = await execute_chat_turn(
                db=db,
                user_id=user_id,
                message=message,
                llm=client,
                holdings=holdings,
                debate_on=debate_on,
                master_on=master_on,
                mode_settings=mode_settings,
                long_term_context=prepared.long_term_context,
                user_context_text=prepared.user_context_text,
                history=history,
                confirmed_symbol=confirmed_symbol,
                confirmed_name=confirmed_name,
                execution_preference=execution_preference,
                user_context=user_context,
                scope=prepared.scope,
                on_progress=on_progress,
            )
            reply = result.reply
            cards = result.cards
            intent = result.intent
            partial = result.partial
        except LLMConfigError as exc:
            logger.warning("LLM config error in chat turn: %s", exc)
            reply = "LLM 未配置，请在设置中填写 API Key 或开启 Mock 模式。"
            partial = True
            await on_progress(
                {
                    "type": "error",
                    "code": "llm_not_configured",
                    "message": str(exc),
                }
            )
        except httpx.RequestError as exc:
            logger.exception("LLM request failed: %s", exc)
            reply = "网络或 LLM 服务暂时不可用，请稍后重试。"
            partial = True
            await on_progress(
                {
                    "type": "error",
                    "code": "llm_request_failed",
                    "message": str(exc),
                }
            )
        except Exception as exc:
            logger.exception("Chat stream turn failed: %s", exc)
            reply = "抱歉，分析过程出错，请稍后重试。"
            partial = True
            await on_progress(
                {
                    "type": "error",
                    "code": "chat_turn_failed",
                    "message": str(exc),
                }
            )
        finally:
            await progress_queue.put(None)

    turn_task = asyncio.create_task(_run_turn())

    while True:
        hint = await progress_queue.get()
        if hint is None:
            break
        yield hint
        if hint.get("type") == "skill_start":
            save_checkpoint(
                db,
                user_id,
                sid,
                {
                    "mode": "skill",
                    "skill_id": hint.get("skill_id"),
                    "skill_run_id": hint.get("skill_run_id"),
                },
            )
        elif hint.get("message_key"):
            save_checkpoint(
                db,
                user_id,
                sid,
                {
                    "mode": "react",
                    "message_key": hint.get("message_key"),
                    "message_params": hint.get("message_params"),
                },
            )

    await turn_task

    yield {
        "type": "done",
        "response": {
            "session_id": sid,
            "reply": reply,
            "cards": cards,
            "intent": intent,
            "partial": partial,
            "llm_usage": usage_to_out(get_usage()),
        },
    }
