"""LangGraph StateGraph orchestrator — direct / debate / plan-execute / risk."""

import asyncio
import logging
import uuid
from typing import Annotated, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from stockresearch.agents.market.research_stream import run_market_research_stream
from stockresearch.agents.orchestrator.complexity import (
    ComplexityResult,
    is_risk_intent,
    resolve_execution_mode,
)
from stockresearch.agents.research.runner import run_research
from stockresearch.agents.orchestrator.plan_execute import PlanExecuteAgent
from stockresearch.agents.orchestrator.react_agent import OrchestratorAgent
from stockresearch.agents.risk.engine import run_risk_checkup
from stockresearch.core.config import get_settings
from stockresearch.core.constants import INTENT_CHAT, INTENT_RISK
from stockresearch.core.schemas import CardPayload, ChatResponse, RiskCheckupOut
from stockresearch.db.models import Conversation, Holding
from stockresearch.services.message_stock import resolve_message_stock, stock_choice_card
from stockresearch.services.stock_lookup import StockLookupResult
from stockresearch.utils.disclaimer import strip_disclaimer
from stockresearch.utils.llm import LLMClient, get_llm_client
from stockresearch.utils.llm_usage import get_usage, reset_usage, usage_to_out

logger = logging.getLogger(__name__)


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
    analysis_mode: str | None
    enable_debate: bool | None
    confirmed_symbol: str | None
    confirmed_name: str | None
    holdings: list[_HoldingInfo]
    holding_objects: list[Holding]
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
            if is_risk_intent(msg) and state["holding_objects"]:
                return {"intent": INTENT_RISK, "mode": "risk"}
            mode = resolve_execution_mode(
                msg,
                state.get("analysis_mode"),
                enable_debate=bool(state.get("enable_debate")),
            )
            return {"intent": INTENT_CHAT, "mode": mode}

        async def node_chat(state: OrchestratorState) -> dict:
            mode = state.get("mode", ComplexityResult.DIRECT)
            msg = state["message"]

            if mode in (ComplexityResult.DEBATE, ComplexityResult.RESEARCH):
                return await _run_stock_research(db, llm, state, with_debate=mode == ComplexityResult.DEBATE)
            if mode in (ComplexityResult.MARKET_DEBATE, ComplexityResult.MARKET_RESEARCH):
                return await _run_market_research(
                    llm,
                    msg,
                    with_debate=mode == ComplexityResult.MARKET_DEBATE,
                )
            if mode == ComplexityResult.PLAN_EXECUTE:
                return await _run_plan_execute(db, llm, state)
            # Default: direct ReAct
            agent = OrchestratorAgent(db=db, llm=llm, user_id=state["user_id"])
            reply, cards = await agent.run(msg)
            return {"cards": cards, "reply": reply}

        async def node_risk(state: OrchestratorState) -> dict:
            holdings = state.get("holding_objects", [])
            try:
                result = await asyncio.wait_for(
                    run_risk_checkup(holdings, llm=llm),
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
        analysis_mode: str | None = None,
        enable_debate: bool | None = None,
        confirmed_symbol: str | None = None,
        confirmed_name: str | None = None,
    ) -> ChatResponse:
        sid = session_id or str(uuid.uuid4())
        holdings = await asyncio.to_thread(
            lambda: self._db.query(Holding).filter(Holding.user_id == user_id).all()
        )
        holdings_data: list[_HoldingInfo] = [
            {"symbol": h.symbol, "name": h.name, "sector": h.sector} for h in holdings
        ]

        initial_state: OrchestratorState = {
            "user_id": user_id,
            "message": message,
            "session_id": sid,
            "intent": INTENT_CHAT,
            "mode": ComplexityResult.DIRECT,
            "analysis_mode": analysis_mode,
            "enable_debate": enable_debate,
            "confirmed_symbol": confirmed_symbol,
            "confirmed_name": confirmed_name,
            "holdings": holdings_data,
            "holding_objects": holdings,
            "cards": [],
            "reply": "",
            "partial": False,
        }

        reset_usage(model=str(getattr(self._llm, "_model", "") or ""))
        final_state = await self._graph.ainvoke(initial_state)

        reply = strip_disclaimer(final_state["reply"])
        if final_state["partial"]:
            reply += "\n\n（部分分析未完成）"

        await asyncio.to_thread(self._save_conversation, user_id, sid, message, reply)

        return ChatResponse(
            session_id=sid,
            reply=reply,
            cards=[CardPayload(type=c["type"], data=c["data"]) for c in final_state["cards"]],
            intent=final_state["intent"],
            partial=final_state["partial"],
            llm_usage=usage_to_out(get_usage()),
        )

    def _save_conversation(self, user_id: int, session_id: str, user_msg: str, reply: str) -> None:
        conv = self._db.query(Conversation).filter(Conversation.session_id == session_id).first()
        if conv is None:
            conv = Conversation(user_id=user_id, session_id=session_id, messages=[])
            self._db.add(conv)
        messages = list(conv.messages)
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": reply})
        conv.messages = messages[-20:]
        self._db.commit()


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

    result = await run_research(resolved.symbol, llm, with_debate=with_debate)
    return {
        "cards": [{"type": "research", "data": result.model_dump(mode="json")}],
        "reply": result.summary,
    }


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
async def _run_plan_execute(db: Session, llm, state: OrchestratorState) -> dict:
    """Run Plan-and-Execute workflow for complex queries."""
    msg = state["message"]

    # Create tool executor that delegates to OrchestratorAgent tools
    react_agent = OrchestratorAgent(db=db, llm=llm, user_id=state["user_id"])

    async def tool_executor(name: str, args: dict) -> str:
        return await react_agent._execute_tool(name, args)

    agent = PlanExecuteAgent(llm=llm, tool_executor=tool_executor)
    reply, plan_cards = await agent.run(msg)

    return {"cards": plan_cards, "reply": reply}
