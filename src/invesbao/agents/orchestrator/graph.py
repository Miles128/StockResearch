"""LangGraph StateGraph orchestrator for multi-agent coordination."""

import asyncio
import logging
import uuid
from typing import Annotated, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from invesbao.agents.news.agent import get_news_for_user
from invesbao.agents.orchestrator.intent_router import route_intent
from invesbao.agents.research.runner import run_research
from invesbao.agents.risk.engine import run_risk_checkup
from invesbao.core.config import get_settings
from invesbao.core.constants import DISCLAIMER, INTENT_CHAT, INTENT_COMPOSITE
from invesbao.core.schemas import CardPayload, ChatResponse, ResearchReportOut, RiskCheckupOut
from invesbao.db.models import Conversation, Holding
from invesbao.services.cache import CacheService
from invesbao.utils.llm import get_llm_client
from invesbao.utils.symbols import resolve_name

logger = logging.getLogger(__name__)


def _append(current: list, update: list) -> list:
    return current + update


def _or_reducer(current: bool, update: bool) -> bool:
    return current or update


class OrchestratorState(TypedDict):
    user_id: int
    message: str
    session_id: str
    intent: str
    symbols: list[str]
    holdings: list[dict[str, object]]
    cards: Annotated[list[dict[str, object]], _append]
    reply: str
    partial: Annotated[bool, _or_reducer]


CHAT_SYSTEM = f"""你是「投小宝」，面向 A 股个人投资者的 AI 投研助手。

表达风格（任何情况下都必须遵守）：
- 简明扼要：每个观点 2～3 句，先思路后结论，不堆砌、不啰嗦
- 娓娓道来：先点结论，再简短说明缘由，逻辑清楚
- 非常客气、亲切、尊重：全程用「您」，语气温和得体
- 用白话，不用 markdown 标题/星号/长列表
- 不给出买入、卖出、加仓、减仓等操作建议
- 需要展示多空观点时，各用一两句概括

每次回复末尾另起一行加上：{DISCLAIMER}"""


async def _run_with_timeout[T](coro, timeout: int) -> tuple[T | None, bool]:
    try:
        result = await asyncio.wait_for(coro, timeout=timeout)
        return result, False
    except TimeoutError:
        return None, True


class Orchestrator:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._cache = CacheService()
        self._llm = get_llm_client()
        self._holdings: list[Holding] = []
        self._graph = self._build_graph()

    def _build_graph(self):
        db = self._db
        cache = self._cache
        llm = self._llm

        def _load_holdings(user_id: int) -> list[Holding]:
            return db.query(Holding).filter(Holding.user_id == user_id).all()

        async def node_route(state: OrchestratorState) -> dict:
            intent, symbols = await route_intent(state["message"], llm)
            if not symbols and state["holdings"]:
                symbols = [str(h["symbol"]) for h in state["holdings"][:1]]
            return {"intent": intent, "symbols": symbols}

        async def node_news(state: OrchestratorState) -> dict:
            related_only = bool(state["symbols"])
            news = await get_news_for_user(
                db,
                state["user_id"],
                related_only=related_only,
                limit=5,
            )
            cards = [{"type": "news", "data": {"items": [n.model_dump(mode="json") for n in news]}}]
            symbol_hint = state["symbols"][0] if state["symbols"] else "市场"
            target = resolve_name(symbol_hint) if symbol_hint != "市场" else "持仓"
            reply = f"已为您整理与{target}相关的最新快讯，请见下方卡片。"
            return {"cards": cards, "reply": reply}

        async def node_research(state: OrchestratorState) -> dict:
            symbol = state["symbols"][0] if state["symbols"] else "600519"
            cache_key = f"research:{symbol}"
            cached = cache.get_json(cache_key)
            partial = False

            if cached:
                report = ResearchReportOut.model_validate({**cached, "cached": True})
            else:
                result, timed_out = await _run_with_timeout(
                    run_research(symbol), get_settings().agent_timeout_seconds
                )
                if timed_out or not isinstance(result, ResearchReportOut):
                    reply = f"抱歉，{resolve_name(symbol)} 的部分分析暂时超时，请您稍后再试。"
                    return {"partial": True, "reply": reply}
                report = result
                cache.set_json(
                    cache_key,
                    report.model_dump(mode="json"),
                    ttl_seconds=get_settings().research_cache_ttl_seconds,
                )

            cards = [{"type": "research", "data": report.model_dump(mode="json")}]
            reply = report.summary
            return {"cards": cards, "reply": reply, "partial": partial}

        async def node_risk(state: OrchestratorState) -> dict:
            holdings = _load_holdings(state["user_id"])
            result, timed_out = await _run_with_timeout(
                run_risk_checkup(holdings, llm=llm),
                get_settings().agent_timeout_seconds,
            )
            partial = timed_out
            if result is None or not isinstance(result, RiskCheckupOut):
                return {"partial": True, "reply": "抱歉，风控体检暂时无法完成，请您稍后再试。"}
            cards = [{"type": "risk", "data": result.model_dump(mode="json")}]
            reply = result.portfolio_summary
            return {"cards": cards, "reply": reply, "partial": partial}

        async def node_composite(state: OrchestratorState) -> dict:
            research_update = await node_research(state)
            temp_state = {**state, **research_update}
            risk_update = await node_risk(temp_state)
            combined_reply = risk_update.get("reply", research_update.get("reply", ""))
            combined_reply += "\n\n另附持仓风控摘要，详见下方卡片。"
            combined_cards = research_update.get("cards", []) + risk_update.get("cards", [])
            combined_partial = (
                research_update.get("partial", False) or risk_update.get("partial", False)
            )
            return {"cards": combined_cards, "reply": combined_reply, "partial": combined_partial}

        async def node_chat(state: OrchestratorState) -> dict:
            reply = await llm.complete(CHAT_SYSTEM, state["message"])
            cards = [{"type": "text", "data": {"content": reply}}]
            return {"cards": cards, "reply": reply}

        graph = StateGraph(OrchestratorState)
        graph.add_node("route", node_route)
        graph.add_node("news", node_news)
        graph.add_node("research", node_research)
        graph.add_node("risk", node_risk)
        graph.add_node("composite", node_composite)
        graph.add_node("chat", node_chat)

        graph.set_entry_point("route")

        graph.add_conditional_edges(
            "route",
            lambda state: state["intent"],
            {
                "news": "news",
                "research": "research",
                "risk": "risk",
                "composite": "composite",
                "chat": "chat",
            },
        )

        for node_name in ("news", "research", "risk", "composite", "chat"):
            graph.add_edge(node_name, END)

        return graph.compile()

    async def run(
        self,
        user_id: int,
        message: str,
        session_id: str | None = None,
    ) -> ChatResponse:
        sid = session_id or str(uuid.uuid4())
        self._holdings = self._db.query(Holding).filter(Holding.user_id == user_id).all()
        holdings_data: list[dict[str, object]] = [
            {"symbol": h.symbol, "name": h.name, "sector": h.sector} for h in self._holdings
        ]

        initial_state: OrchestratorState = {
            "user_id": user_id,
            "message": message,
            "session_id": sid,
            "intent": INTENT_CHAT,
            "symbols": [],
            "holdings": holdings_data,
            "cards": [],
            "reply": "",
            "partial": False,
        }

        final_state = await self._graph.ainvoke(initial_state)

        reply = final_state["reply"]
        if final_state["partial"]:
            reply += "\n\n（部分分析未完成）"

        if not self._holdings and final_state["intent"] in ("news", "risk", INTENT_COMPOSITE):
            reply += (
                "\n\n💡 未检测到持仓记录。请在「持仓」页添加股票，"
                "或在「快讯」页选择关注板块。"
            )

        self._save_conversation(user_id, sid, message, reply)

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
