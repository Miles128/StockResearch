"""Streaming chat orchestrator — real-time status while routing agents."""

import uuid
from collections.abc import AsyncIterator

from sqlalchemy.orm import Session

from invesbao.agents.news.agent import get_news_for_user
from invesbao.agents.orchestrator.intent_router import route_intent
from invesbao.agents.orchestrator.graph import CHAT_SYSTEM, Orchestrator
from invesbao.agents.research.stream import run_research_stream
from invesbao.agents.risk.stream import run_risk_checkup_stream
from invesbao.core.constants import INTENT_CHAT, INTENT_COMPOSITE
from invesbao.core.schemas import CardPayload, ChatResponse, ResearchReportOut, RiskCheckupOut
from invesbao.db.models import Holding
from invesbao.utils.llm import get_llm_client
from invesbao.utils.symbols import resolve_name

_INTENT_LABELS = {
    "news": "快讯",
    "research": "投研",
    "risk": "风控",
    "composite": "投研+风控",
    "chat": "对话",
}


async def run_chat_stream(
    db: Session,
    user_id: int,
    message: str,
    session_id: str | None = None,
) -> AsyncIterator[dict[str, object]]:
    sid = session_id or str(uuid.uuid4())
    llm = get_llm_client()
    holdings = db.query(Holding).filter(Holding.user_id == user_id).all()
    holdings_data = [
        {"symbol": h.symbol, "name": h.name, "sector": h.sector} for h in holdings
    ]

    yield {"type": "status", "message": "正在理解您的问题…"}

    intent, symbols = await route_intent(message, llm)
    if not symbols and holdings_data:
        symbols = [str(holdings_data[0]["symbol"])]

    intent_label = _INTENT_LABELS.get(intent, intent)
    yield {
        "type": "status",
        "message": f"已为您路由至「{intent_label}」",
        "intent": intent,
    }

    cards: list[dict[str, object]] = []
    reply = ""
    partial = False

    if intent == "news":
        yield {"type": "agent_start", "agent_id": "news", "agent_name": "快讯 Agent", "role": "analyst"}
        related_only = bool(symbols)
        news = await get_news_for_user(db, user_id, related_only=related_only, limit=5)
        target = resolve_name(symbols[0]) if symbols else "持仓"
        cards = [{"type": "news", "data": {"items": [n.model_dump(mode="json") for n in news]}}]
        reply = f"已为您整理与{target}相关的最新快讯，请见下方卡片。"
        yield {
            "type": "agent_done",
            "agent_id": "news",
            "agent_name": "快讯 Agent",
            "role": "analyst",
            "content": f"已筛选 {len(news)} 条",
        }

    elif intent == "research":
        symbol = symbols[0] if symbols else "600519"
        async for event in run_research_stream(symbol, llm=llm):
            if event.get("type") == "done":
                payload = event.get("result")
                if isinstance(payload, dict):
                    report = ResearchReportOut.model_validate(payload)
                    cards = [{"type": "research", "data": report.model_dump(mode="json")}]
                    reply = report.summary
            else:
                yield event

    elif intent == "risk":
        async for event in run_risk_checkup_stream(holdings, llm=llm):
            if event.get("type") == "done":
                payload = event.get("result")
                if isinstance(payload, dict):
                    result = RiskCheckupOut.model_validate(payload)
                    cards = [{"type": "risk", "data": result.model_dump(mode="json")}]
                    reply = result.portfolio_summary
            else:
                yield event

    elif intent == INTENT_COMPOSITE:
        symbol = symbols[0] if symbols else "600519"
        async for event in run_research_stream(symbol, llm=llm):
            if event.get("type") == "done":
                payload = event.get("result")
                if isinstance(payload, dict):
                    report = ResearchReportOut.model_validate(payload)
                    cards.append({"type": "research", "data": report.model_dump(mode="json")})
                    reply = report.summary
            else:
                yield event
        yield {"type": "status", "message": "投研完成，继续风控体检…"}
        async for event in run_risk_checkup_stream(holdings, llm=llm):
            if event.get("type") == "done":
                payload = event.get("result")
                if isinstance(payload, dict):
                    result = RiskCheckupOut.model_validate(payload)
                    cards.append({"type": "risk", "data": result.model_dump(mode="json")})
                    reply += f"\n\n{result.portfolio_summary}"
            else:
                yield event

    else:
        yield {
            "type": "agent_start",
            "agent_id": "chat",
            "agent_name": "投小宝",
            "role": "analyst",
        }
        yield {"type": "status", "message": "正在为您组织回复…"}
        reply = await llm.complete(CHAT_SYSTEM, message)
        cards = [{"type": "text", "data": {"content": reply}}]
        yield {
            "type": "agent_done",
            "agent_id": "chat",
            "agent_name": "投小宝",
            "role": "analyst",
            "content": "回复已就绪",
        }

    if partial:
        reply += "\n\n（部分分析未完成）"
    if not holdings and intent in ("news", "risk", INTENT_COMPOSITE):
        reply += (
            "\n\n💡 您尚未录入持仓。请在「持仓」页添加，或在「快讯」页选择关注板块。"
        )

    yield {"type": "reply", "content": reply}

    response = ChatResponse(
        session_id=sid,
        reply=reply,
        cards=[CardPayload(type=c["type"], data=c["data"]) for c in cards],  # type: ignore[arg-type]
        intent=intent,
        partial=partial,
    )
    Orchestrator(db)._save_conversation(user_id, sid, message, reply)
    yield {"type": "done", "response": response.model_dump(mode="json")}
