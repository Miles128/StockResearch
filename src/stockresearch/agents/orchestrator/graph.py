"""LangGraph StateGraph orchestrator — direct / debate / plan-execute / risk."""

import asyncio
import uuid
from typing import Annotated, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from stockresearch.agents.industry.research import run_industry_research
from stockresearch.agents.market.research_stream import run_market_research_stream
from stockresearch.agents.orchestrator.complexity import (
    ComplexityResult,
    extract_industry_sector,
    is_risk_intent,
)
from stockresearch.agents.orchestrator.plan_execute import PlanExecuteAgent
from stockresearch.agents.orchestrator.react_agent import OrchestratorAgent
from stockresearch.agents.orchestrator.route_plan import (
    resolve_mode_with_preference,
)
from stockresearch.agents.research.runner import run_research
from stockresearch.agents.risk.engine import run_risk_checkup
from stockresearch.core.config import get_settings
from stockresearch.core.constants import INTENT_CHAT, INTENT_RISK
from stockresearch.core.schemas import ChatResponse, ChatUserContext, ModeSettingsOut, RiskCheckupOut
from stockresearch.db.models import Holding
from stockresearch.services.chat_context import build_long_term_context, format_user_context_block
from stockresearch.services.chat_response import assemble_chat_response, save_conversation
from stockresearch.services.conversation_memory import prepare_chat_history
from stockresearch.services.message_stock import resolve_message_stock, stock_choice_card
from stockresearch.services.stock_lookup import StockLookupResult
from stockresearch.services.user_preferences import get_mode_settings
from stockresearch.utils.llm import LLMClient, get_llm_client
from stockresearch.utils.llm_usage import get_usage, reset_usage, usage_to_out


def _append(current: list, update: list) -> list:
    return current + update


def _or_reducer(current: bool, update: bool) -> bool:
    return current or update


class _HoldingInfo(TypedDict):
    symbol: str
    name: str
    sector: str


class OrchestratorState(TypedDict):
    user_id: int
    message: str
    session_id: str
    intent: str
    mode: str  # direct / debate / plan_execute
    enable_debate: bool | None
    enable_master_commentary: bool | None
    user_context: ChatUserContext | None
    mode_settings: ModeSettingsOut
    long_term_context: str
    user_context_text: str
    history: list[dict[str, str]]
    confirmed_symbol: str | None
    confirmed_name: str | None
    execution_preference: str | None
    finance_tools: bool
    holdings: list[_HoldingInfo]
    cards: Annotated[list[dict[str, object]], _append]
    reply: str
    partial: Annotated[bool, _or_reducer]


class Orchestrator:
    def __init__(self, db: Session, llm: LLMClient | None = None) -> None:
        self._db = db
        self._llm = llm or get_llm_client()
        self._graph = self._build_graph()

    def _build_graph(self):
        db = self._db
        llm = self._llm

        async def node_route(state: OrchestratorState) -> dict:
            msg = state["message"].strip()
            # Risk keywords → risk intent
            if is_risk_intent(msg) and state["holdings"]:
                return {"intent": INTENT_RISK, "mode": "risk"}
            mode, finance_tools = resolve_mode_with_preference(
                msg,
                state.get("execution_preference"),
                enable_debate=(
                    True
                    if state.get("enable_debate") is None
                    else bool(state.get("enable_debate"))
                ),
            )
            return {"intent": INTENT_CHAT, "mode": mode, "finance_tools": finance_tools}

        async def node_chat(state: OrchestratorState) -> dict:
            mode = state.get("mode", ComplexityResult.DIRECT)
            msg = state["message"]

            if mode in (ComplexityResult.DEBATE, ComplexityResult.RESEARCH):
                return await _run_stock_research(
                    db, llm, state, with_debate=mode == ComplexityResult.DEBATE
                )
            if mode in (ComplexityResult.MARKET_DEBATE, ComplexityResult.MARKET_RESEARCH):
                return await _run_market_research(
                    llm,
                    msg,
                    with_debate=mode == ComplexityResult.MARKET_DEBATE,
                )
            if mode == ComplexityResult.PLAN_EXECUTE:
                return await _run_plan_execute(db, llm, state)
            if mode == ComplexityResult.INDUSTRY_RESEARCH:
                return await _run_industry_research(db, llm, state)
            if mode == "route_choice":
                return {}
            # Default: direct ReAct
            finance_tools = bool(state.get("finance_tools", True))
            agent = OrchestratorAgent(
                db=db,
                llm=llm,
                user_id=state["user_id"],
                finance_tools=finance_tools,
                mode_settings=state["mode_settings"],
            )
            reply, cards = await agent.run(
                msg,
                history=state.get("history"),
                long_term_context=state.get("long_term_context", ""),
                user_context_text=state.get("user_context_text", ""),
            )
            return {"cards": cards, "reply": reply}

        async def node_risk(state: OrchestratorState) -> dict:
            holdings = await asyncio.to_thread(
                lambda: db.query(Holding).filter(Holding.user_id == state["user_id"]).all()
            )
            settings = state["mode_settings"]
            master_on = (
                bool(state["enable_master_commentary"])
                if state.get("enable_master_commentary") is not None
                else bool(settings.enable_master_commentary)
            )
            try:
                result = await asyncio.wait_for(
                    run_risk_checkup(
                        holdings,
                        llm=llm,
                        enable_master_commentary=master_on,
                        mode_settings=settings,
                    ),
                    timeout=get_settings().agent_timeout_seconds,
                )
            except TimeoutError:
                return {"partial": True, "reply": "抱歉，风控体检超时，请您稍后再试。"}
            if not isinstance(result, RiskCheckupOut):
                return {"partial": True, "reply": "抱歉，风控体检暂时无法完成，请您稍后再试。"}
            cards = [{"type": "risk", "data": result.model_dump(mode="json")}]
            reply = result.portfolio_summary
            return {"cards": cards, "reply": reply}

        graph = StateGraph(OrchestratorState)
        graph.add_node("route", node_route)
        graph.add_node("chat", node_chat)
        graph.add_node("risk", node_risk)

        graph.set_entry_point("route")

        graph.add_conditional_edges(
            "route",
            lambda state: state["intent"],
            {
                "chat": "chat",
                "risk": "risk",
            },
        )

        graph.add_edge("chat", END)
        graph.add_edge("risk", END)

        return graph.compile()

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
        long_term_context = await build_long_term_context(mode_settings=settings, holdings=holdings)
        user_context_text = format_user_context_block(user_context)
        history = await prepare_chat_history(self._db, user_id, sid, self._llm)
        holdings_data: list[_HoldingInfo] = [
            {"symbol": h.symbol, "name": h.name, "sector": h.sector} for h in holdings
        ]

        initial_state: OrchestratorState = {
            "user_id": user_id,
            "message": message,
            "session_id": sid,
            "intent": INTENT_CHAT,
            "mode": ComplexityResult.DIRECT,
            "enable_debate": enable_debate,
            "enable_master_commentary": enable_master_commentary,
            "user_context": user_context,
            "mode_settings": settings,
            "long_term_context": long_term_context,
            "user_context_text": user_context_text,
            "history": history,
            "confirmed_symbol": confirmed_symbol,
            "confirmed_name": confirmed_name,
            "execution_preference": execution_preference,
            "finance_tools": True,
            "holdings": holdings_data,
            "cards": [],
            "reply": "",
            "partial": False,
        }

        reset_usage(model=str(getattr(self._llm, "_model", "") or ""))
        final_state = await self._graph.ainvoke(initial_state)

        intent = final_state["intent"]
        for card in final_state["cards"]:
            card_type = card.get("type")
            if card_type == "research":
                intent = "research"
                break
            if card_type == "risk":
                intent = INTENT_RISK
                break

        response = assemble_chat_response(
            session_id=sid,
            reply=final_state["reply"],
            cards=final_state["cards"],
            intent=intent,
            partial=final_state["partial"],
            llm_usage=usage_to_out(get_usage()),
        )

        await asyncio.to_thread(
            save_conversation,
            self._db,
            user_id,
            sid,
            message,
            response.reply,
        )

        return response

# ── Research modes ───────────────────────────────────────
async def _run_stock_research(
    db: Session,
    llm,
    state: OrchestratorState,
    *,
    with_debate: bool,
) -> dict:
    msg = state["message"]
    resolved = await resolve_message_stock(
        msg,
        llm,
        confirmed_symbol=state.get("confirmed_symbol"),
        confirmed_name=state.get("confirmed_name"),
    )
    if isinstance(resolved, StockLookupResult):
        card = stock_choice_card(msg, resolved)
        return {"cards": [card], "reply": resolved.message}

    result = await run_research(
        resolved.symbol,
        llm,
        with_debate=with_debate,
        enable_master_commentary=_master_enabled(state),
        mode_settings=state["mode_settings"],
    )
    return {
        "cards": [{"type": "research", "data": result.model_dump(mode="json")}],
        "reply": result.summary,
    }


def _master_enabled(state: OrchestratorState) -> bool:
    settings = state["mode_settings"]
    if state.get("enable_master_commentary") is not None:
        return bool(state["enable_master_commentary"])
    return bool(settings.enable_master_commentary)


async def _run_market_research(
    llm,
    message: str,
    *,
    with_debate: bool,
) -> dict:
    payload: dict[str, object] | None = None
    async for event in run_market_research_stream(message, llm=llm, with_debate=with_debate):
        if event.get("type") == "done":
            raw = event.get("result")
            if isinstance(raw, dict):
                payload = raw
    if payload is None:
        return {"cards": [], "reply": "市场深度投研暂时无法完成，请稍后重试。"}
    summary = str(payload.get("summary", ""))
    return {
        "cards": [{"type": "research", "data": payload}],
        "reply": summary,
    }


# ── Plan-Execute mode ────────────────────────────────────
async def _run_industry_research(db: Session, llm, state: OrchestratorState) -> dict:
    msg = state["message"]
    sectors = [h["sector"] for h in state.get("holdings", [])]
    sector = extract_industry_sector(msg, sectors) or "行业"
    reply, cards = await run_industry_research(db, llm, state["user_id"], sector, msg)
    return {"cards": cards, "reply": reply}


async def _run_plan_execute(db: Session, llm, state: OrchestratorState) -> dict:
    """Run Plan-and-Execute workflow for complex queries."""
    msg = state["message"]

    # Create tool executor that delegates to OrchestratorAgent tools
    finance_tools = bool(state.get("finance_tools", True))
    react_agent = OrchestratorAgent(
        db=db,
        llm=llm,
        user_id=state["user_id"],
        finance_tools=finance_tools,
        mode_settings=state["mode_settings"],
    )

    async def tool_executor(name: str, args: dict) -> str:
        return await react_agent._execute_tool(name, args)

    agent = PlanExecuteAgent(
        llm=llm, tool_executor=tool_executor, finance_tools=finance_tools
    )
    reply, plan_cards = await agent.run(
        msg,
        history=state.get("history"),
        long_term_context=state.get("long_term_context", ""),
        user_context_text=state.get("user_context_text", ""),
    )

    return {"cards": plan_cards, "reply": reply}
