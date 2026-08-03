"""Sync chat orchestrator — skill-first ReAct / plan-execute / risk."""

import asyncio
import uuid

from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.chat_execute import execute_chat_turn
from stockresearch.core.constants import INTENT_CHAT, INTENT_RISK
from stockresearch.core.schemas import ChatUserContext, ChatResponse, ModeSettingsOut
from stockresearch.db.models import Holding
from stockresearch.services.chat_scope import prepare_chat_turn
from stockresearch.services.chat_response import assemble_chat_response, save_conversation
from stockresearch.services.conversation_memory import prepare_chat_history
from stockresearch.services.user_preferences import get_mode_settings
from stockresearch.utils.llm import LLMClient, get_llm_client
from stockresearch.utils.llm_usage import get_usage, reset_usage, usage_to_out


class Orchestrator:
    def __init__(self, db: Session, llm: LLMClient | None = None) -> None:
        self._db = db
        self._llm = llm or get_llm_client()

    async def run(
        self,
        user_id: int,
        message: str,
        session_id: str | None = None,
        enable_debate: bool | None = None,
        enable_master_commentary: bool | None = None,
        user_context: ChatUserContext | None = None,
        mode_settings: ModeSettingsOut | None = None,
        confirmed_symbol: str | None = None,
        confirmed_name: str | None = None,
        execution_preference: str | None = None,
    ) -> ChatResponse:
        sid = session_id or str(uuid.uuid4())
        holdings = await asyncio.to_thread(
            lambda: self._db.query(Holding).filter(Holding.user_id == user_id).all()
        )
        settings = mode_settings or get_mode_settings(self._db, user_id)
        prepared = await prepare_chat_turn(
            mode_settings=settings,
            holdings=holdings,
            message=message,
            user_context=user_context,
            llm=self._llm,
            confirmed_symbol=confirmed_symbol,
            confirmed_name=confirmed_name,
        )
        history = await prepare_chat_history(self._db, user_id, sid, self._llm)

        debate_on = (
            settings.enable_debate if enable_debate is None else bool(enable_debate)
        )
        master_on = (
            bool(enable_master_commentary)
            if enable_master_commentary is not None
            else bool(settings.enable_master_commentary)
        )

        reset_usage(model=str(getattr(self._llm, "_model", "") or ""))
        result = await execute_chat_turn(
            db=self._db,
            user_id=user_id,
            message=prepared.message,
            llm=self._llm,
            holdings=prepared.holdings,
            debate_on=debate_on,
            master_on=master_on,
            mode_settings=settings,
            long_term_context=prepared.long_term_context,
            user_context_text=prepared.user_context_text,
            history=history,
            confirmed_symbol=confirmed_symbol,
            confirmed_name=confirmed_name,
            execution_preference=execution_preference,
            user_context=user_context,
            scope=prepared.scope,
        )

        intent = INTENT_CHAT
        for card in result.cards:
            card_type = card.get("type")
            if card_type == "research":
                intent = "research"
                break
            if card_type == "risk":
                intent = INTENT_RISK
                break

        response = assemble_chat_response(
            session_id=sid,
            reply=result.reply,
            cards=result.cards,
            intent=intent,
            partial=result.partial,
            llm_usage=usage_to_out(get_usage()),
        )

        await asyncio.to_thread(
            save_conversation,
            self._db,
            user_id,
            sid,
            prepared.message,
            response.reply,
        )

        return response
