"""LangGraph StateGraph orchestrator — direct / debate / plan-execute / risk."""

import asyncio
import logging
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
from stockresearch.core.schemas import CardPayload, ChatResponse, RiskCheckupOut
from stockresearch.db.models import Conversation, Holding
from stockresearch.services.message_stock import resolve_message_stock, stock_choice_card
from stockresearch.services.stock_lookup import StockLookupResult
from stockresearch.agents.orchestrator.balance_check import check_balance
from stockresearch.agents.output_style import get_reading_mode
from stockresearch.services.glossary import mark_terms
from stockresearch.services.neutral_guard import neutral_guard
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
                analysis_mode=state.get("analysis_mode"),
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
                return await _run_stock_research(db, llm, state, with_debate=mode == ComplexityResult.DEBATE)
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
                db=db, llm=llm, user_id=state["user_id"], finance_tools=finance_tools
            )
            reply, cards = await agent.run(msg)
            return {"cards": cards, "reply": reply}

        async def node_risk(state: OrchestratorState) -> dict:
            holdings = await asyncio.to_thread(
                lambda: db.query(Holding).filter(Holding.user_id == state["user_id"]).all()
            )
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
        execution_preference: str | None = None,
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
            "execution_preference": execution_preference,
            "finance_tools": True,
            "holdings": holdings_data,
            "cards": [],
            "reply": "",
            "partial": False,
        }

        reset_usage(model=str(getattr(self._llm, "_model", "") or ""))
        final_state = await self._graph.ainvoke(initial_state)

        reply = strip_disclaimer(final_state["reply"])
        # Apply neutral guard → balance check → glossary marking
        reply = neutral_guard(reply)
        reply = check_balance(reply)
        if get_reading_mode() == "professional":
            reply = mark_terms(reply)
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
        try:
            conv = self._db.query(Conversation).filter(Conversation.session_id == session_id).first()
            if conv is None:
                conv = Conversation(user_id=user_id, session_id=session_id, messages=[])
                self._db.add(conv)
            messages = list(conv.messages)
            messages.append({"role": "user", "content": user_msg})
            messages.append({"role": "assistant", "content": reply})
            conv.messages = messages[-20:]
            self._db.commit()
        except Exception:
            logger.warning("Failed to save conversation for session %s", session_id, exc_info=True)
            try:
                self._db.rollback()
            except Exception:
                pass


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
        db=db, llm=llm, user_id=state["user_id"], finance_tools=finance_tools
    )

    async def tool_executor(name: str, args: dict) -> str:
        return await react_agent._execute_tool(name, args)

    agent = PlanExecuteAgent(
        llm=llm, tool_executor=tool_executor, finance_tools=finance_tools
    )
    reply, plan_cards = await agent.run(msg)

    return {"cards": plan_cards, "reply": reply}
