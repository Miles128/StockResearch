"""LangGraph StateGraph orchestrator — direct / debate / plan-execute / risk."""

import asyncio
import logging
import uuid
from typing import Annotated, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from stockresearch.agents.debate.agent import DebateAgent
from stockresearch.agents.orchestrator.complexity import (
    ComplexityResult,
    is_risk_intent,
    resolve_execution_mode,
)
from stockresearch.agents.orchestrator.plan_execute import PlanExecuteAgent
from stockresearch.agents.orchestrator.react_agent import OrchestratorAgent
from stockresearch.agents.risk.engine import run_risk_checkup
from stockresearch.core.config import get_settings
from stockresearch.core.constants import INTENT_CHAT, INTENT_RISK
from stockresearch.core.schemas import CardPayload, ChatResponse, RiskCheckupOut
from stockresearch.data.providers.market import QuoteProvider
from stockresearch.db.models import Conversation, Holding
from stockresearch.utils.llm import LLMClient, get_llm_client

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
            mode = resolve_execution_mode(msg, state.get("analysis_mode"))
            return {"intent": INTENT_CHAT, "mode": mode}

        async def node_chat(state: OrchestratorState) -> dict:
            mode = state.get("mode", ComplexityResult.DIRECT)
            msg = state["message"]

            if mode == ComplexityResult.DEBATE:
                return await _run_debate(db, llm, state)
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
            "holdings": holdings_data,
            "holding_objects": holdings,
            "cards": [],
            "reply": "",
            "partial": False,
        }

        final_state = await self._graph.ainvoke(initial_state)

        reply = final_state["reply"]
        if final_state["partial"]:
            reply += "\n\n（部分分析未完成）"

        await asyncio.to_thread(self._save_conversation, user_id, sid, message, reply)

        return ChatResponse(
            session_id=sid,
            reply=reply,
            cards=[CardPayload(type=c["type"], data=c["data"]) for c in final_state["cards"]],
            intent=final_state["intent"],
            partial=final_state["partial"],
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


# ── Debate mode ──────────────────────────────────────────
async def _run_debate(db: Session, llm, state: OrchestratorState) -> dict:
    """Run multi-agent debate for stock-specific queries."""
    msg = state["message"]
    cards: list[dict[str, object]] = []

    # Extract symbol from message
    symbol, name = await _extract_symbol(db, llm, msg)
    if not symbol:
        # Fallback to direct mode
        agent = OrchestratorAgent(db=db, llm=llm, user_id=state["user_id"])
        reply, agent_cards = await agent.run(msg)
        return {"cards": agent_cards, "reply": reply}

    # Get market data for context
    market_data = ""
    try:
        provider = QuoteProvider()
        quote = await provider.get_quote(symbol)
        arrow = "↑" if quote.change_pct > 0 else "↓" if quote.change_pct < 0 else "→"
        market_data = (
            f"{quote.name}({quote.symbol}) 现价{quote.price:.2f} "
            f"{arrow}{quote.change_pct:+.2f}%\n"
            f"最高{quote.high:.2f} 最低{quote.low:.2f} "
            f"成交量{quote.volume:.0f}"
        )
    except Exception:
        pass

    # Get financial ratios for context
    financial_context = ""
    try:
        from stockresearch.agents.financial.agent import FinancialRatioAgent

        fin_agent = FinancialRatioAgent(llm=None)
        fin_result = await fin_agent.run(symbol, name)
        ratios = fin_result.get("ratios", [])
        if ratios:
            ratio_lines = [
                f"  {r['name']}: {r['value']} ({r['assessment']})"
                for r in ratios
            ]
            financial_context = "财报比率：\n" + "\n".join(ratio_lines)
            # Add financial card
            cards.append({"type": "financial", "data": fin_result})
    except Exception:
        pass

    # Combine context for debate
    full_context = market_data
    if financial_context:
        full_context += "\n\n" + financial_context

    # Run debate
    debate = DebateAgent(llm)
    result = await debate.run_debate(symbol, name, full_context)

    cards.append({"type": "debate", "data": result})

    # Build reply from synthesis
    reply = result.get("synthesis", "")
    if not reply:
        vote = result.get("vote_tally", {})
        bias = result.get("final_bias", "neutral")
        bias_cn = {"bullish": "偏多", "bearish": "偏空", "neutral": "中性"}.get(bias, "中性")
        reply = (
            f"多Agent辩论完成。"
            f"投票结果：看多{vote.get('看多', 0)}票，"
            f"看空{vote.get('看空', 0)}票，"
            f"中性{vote.get('中性', 0)}票。"
            f"综合倾向：{bias_cn}。\n\n"
            "以上内容由 AI 生成，仅供参考，不构成投资建议。"
        )

    return {"cards": cards, "reply": reply}


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


# ── Symbol extraction ────────────────────────────────────
async def _extract_symbol(db: Session, llm, message: str) -> tuple[str, str]:
    """Try to extract stock symbol from message."""
    import re

    # Direct 6-digit code
    match = re.search(r"\b(\d{6})\b", message)
    if match:
        symbol = match.group(1)
        try:
            provider = QuoteProvider()
            quote = await provider.get_quote(symbol)
            return symbol, quote.name
        except Exception:
            return symbol, symbol

    # Common stock names
    stock_names = {
        "茅台": ("600519", "贵州茅台"),
        "宁德时代": ("300750", "宁德时代"),
        "比亚迪": ("002594", "比亚迪"),
        "招商银行": ("600036", "招商银行"),
        "平安银行": ("000001", "平安银行"),
        "中芯国际": ("688981", "中芯国际"),
        "腾讯": ("00700", "腾讯控股"),
        "阿里": ("09988", "阿里巴巴"),
    }
    for name, (sym, full_name) in stock_names.items():
        if name in message:
            return sym, full_name

    return "", ""
