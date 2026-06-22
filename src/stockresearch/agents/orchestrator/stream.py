"""Streaming chat orchestrator — real-time progress + ReAct/Debate/PlanExecute."""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator

from sqlalchemy.orm import Session

from stockresearch.agents.industry.stream import run_industry_research_stream
from stockresearch.agents.market.research_stream import run_market_research_stream
from stockresearch.agents.orchestrator.complexity import (
    ComplexityResult,
    extract_industry_sector,
    is_risk_intent,
    is_stock_analysis_intent,
)
from stockresearch.agents.orchestrator.plan_execute import PlanExecuteAgent
from stockresearch.agents.orchestrator.react_agent import OrchestratorAgent
from stockresearch.agents.orchestrator.route_plan import (
    resolve_mode_with_preference,
)
from stockresearch.agents.research.stream import run_research_stream
from stockresearch.agents.risk.stream import run_risk_checkup_stream
from stockresearch.core.constants import INTENT_RISK
from stockresearch.core.exceptions import LLMConfigError
from stockresearch.core.schemas import CardPayload, ChatResponse, ResearchReportOut, RiskCheckupOut
from stockresearch.db.models import Conversation, Holding
from stockresearch.i18n.status_events import status_event
from stockresearch.services.message_stock import (
    ResolvedStock,
    match_holding_in_message,
    resolve_message_stock,
    stock_choice_card,
)
from stockresearch.services.stock_lookup import StockLookupResult
from stockresearch.services.stream_checkpoint import clear_checkpoint, save_checkpoint
from stockresearch.utils.disclaimer import strip_disclaimer
from stockresearch.utils.llm import LLMClient, get_llm_client
from stockresearch.utils.llm_usage import get_usage, reset_usage, usage_to_out

logger = logging.getLogger(__name__)


def _llm_model_name(client: LLMClient) -> str:
    return str(getattr(client, "_model", "") or "")


async def run_chat_stream(
    db: Session,
    user_id: int,
    message: str,
    session_id: str | None = None,
    llm: LLMClient | None = None,
    analysis_mode: str | None = None,
    enable_debate: bool | None = None,
    confirmed_symbol: str | None = None,
    confirmed_name: str | None = None,
    execution_preference: str | None = None,
) -> AsyncIterator[dict[str, object]]:
    """Yield SSE events with real-time progress updates."""
    sid = session_id or str(uuid.uuid4())
    client = llm or get_llm_client()
    reset_usage(model=_llm_model_name(client))
    holdings = db.query(Holding).filter(Holding.user_id == user_id).all()

    yield status_event("status.understanding")

    msg = message.strip()
    is_risk = is_risk_intent(msg) and bool(holdings)

    debate_on = True if enable_debate is None else bool(enable_debate)

    cards: list[dict[str, object]] = []
    reply = ""
    partial = False
    intent = INTENT_RISK if is_risk else "chat"

    try:
        async for event in _run_chat_stream_body(
            db=db,
            user_id=user_id,
            message=msg,
            sid=sid,
            client=client,
            holdings=holdings,
            is_risk=is_risk,
            debate_on=debate_on,
            analysis_mode=analysis_mode,
            confirmed_symbol=confirmed_symbol,
            confirmed_name=confirmed_name,
            execution_preference=execution_preference,
        ):
            if isinstance(event, dict) and event.get("type") == "done" and "response" in event:
                response = event["response"]
                if isinstance(response, dict):
                    reply = str(response.get("reply", ""))
                    cards = list(response.get("cards", []))
                    intent = str(response.get("intent", intent))
                    partial = bool(response.get("partial", False))
            yield event
    except LLMConfigError as exc:
        logger.warning("LLM config error in chat stream: %s", exc)
        yield {
            "type": "error",
            "code": "llm_not_configured",
            "message": str(exc),
        }
        return

    if partial:
        reply += "\n\n（部分分析未完成）"

    reply = strip_disclaimer(reply)

    response = ChatResponse(
        session_id=sid,
        reply=reply,
        cards=[CardPayload(type=c["type"], data=c["data"]) for c in cards],  # type: ignore[arg-type]
        intent=intent,
        partial=partial,
        llm_usage=usage_to_out(get_usage()),
    )
    clear_checkpoint(db, user_id, sid)

    _save_conversation_async(db, user_id, sid, message, reply)

    yield {"type": "done", "response": response.model_dump(mode="json")}


async def _run_chat_stream_body(
    *,
    db: Session,
    user_id: int,
    message: str,
    sid: str,
    client: LLMClient,
    holdings: list[Holding],
    is_risk: bool,
    debate_on: bool,
    analysis_mode: str | None,
    confirmed_symbol: str | None,
    confirmed_name: str | None,
    execution_preference: str | None,
) -> AsyncIterator[dict[str, object]]:
    """Inner chat stream body. Raises LLMConfigError if API key missing."""
    if is_risk:
        yield status_event("status.routed_risk")
        async for event in run_risk_checkup_stream(holdings, llm=client):
            if event.get("type") == "done":
                payload = event.get("result")
                if isinstance(payload, dict):
                    result = RiskCheckupOut.model_validate(payload)
                    cards = [{"type": "risk", "data": result.model_dump(mode="json")}]
                    reply = result.portfolio_summary
                    yield {
                        "type": "done",
                        "response": {
                            "session_id": sid,
                            "reply": reply,
                            "cards": cards,
                            "intent": INTENT_RISK,
                            "partial": False,
                            "llm_usage": usage_to_out(get_usage()),
                        },
                    }
                    return
            else:
                yield event
        return

    mode, finance_tools = resolve_mode_with_preference(
        message,
        execution_preference,
        analysis_mode=analysis_mode,
        enable_debate=debate_on,
    )
    route_symbol = confirmed_symbol
    route_name = confirmed_name
    mode, route_symbol, route_name = await _upgrade_stock_research_route(
        message,
        client,
        holdings,
        mode=mode,
        debate_on=debate_on,
        execution_preference=execution_preference,
        confirmed_symbol=route_symbol,
        confirmed_name=route_name,
    )
    yield status_event(
        "status.route",
        debate="on" if debate_on else "off",
        mode=str(mode),
    )

    # 收集子流的最终结果（cards/reply/result），统一转换为标准 done 事件。
    cards: list[dict[str, object]] = []
    reply = ""
    intent = "chat"

    def _finalize_from_event(event: dict[str, object]) -> None:
        """Extract cards/reply from sub-stream done event into local vars."""
        nonlocal cards, reply, intent
        if "result" in event and isinstance(event["result"], dict):
            payload = event["result"]
            # Research/market/industry streams return a report dict.
            try:
                report = ResearchReportOut.model_validate(payload)
                cards = [{"type": "research", "data": payload}]
                reply = report.summary
                intent = "research"
            except Exception:
                # Risk stream returns a risk checkup dict.
                try:
                    result = RiskCheckupOut.model_validate(payload)
                    cards = [{"type": "risk", "data": result.model_dump(mode="json")}]
                    reply = result.portfolio_summary
                    intent = "risk"
                except Exception:
                    cards = []
                    reply = ""
        elif "cards" in event or "reply" in event:
            ev_cards = event.get("cards")
            if isinstance(ev_cards, list):
                cards = list(ev_cards)
            ev_reply = event.get("reply")
            if isinstance(ev_reply, str):
                reply = ev_reply

    if mode in (ComplexityResult.MARKET_DEBATE, ComplexityResult.MARKET_RESEARCH):
        intent = "research"
        async for event in _run_market_research_stream(
            client,
            message,
            with_debate=mode == ComplexityResult.MARKET_DEBATE,
        ):
            if event.get("type") == "done":
                _finalize_from_event(event)
            else:
                yield event
    elif mode in (ComplexityResult.DEBATE, ComplexityResult.RESEARCH):
        intent = "research"
        async for event in _run_stock_research_stream(
            client,
            message,
            with_debate=mode == ComplexityResult.DEBATE,
            confirmed_symbol=route_symbol,
            confirmed_name=route_name,
        ):
            if event.get("type") == "done":
                _finalize_from_event(event)
            else:
                yield event
    elif mode == ComplexityResult.PLAN_EXECUTE:
        async for event in _run_plan_execute_stream(
            db, client, message, user_id, sid, finance_tools=finance_tools
        ):
            if event.get("type") == "done":
                _finalize_from_event(event)
            else:
                yield event
    elif mode == ComplexityResult.INDUSTRY_RESEARCH:
        intent = "research"
        sectors = [h.sector for h in holdings]
        sector = extract_industry_sector(message, sectors) or "行业"
        save_checkpoint(db, user_id, sid, {"mode": mode, "sector": sector, "message": message})
        async for event in _run_industry_research_stream(
            db, client, user_id, sector, message, sid, with_debate=debate_on
        ):
            if event.get("type") == "done":
                _finalize_from_event(event)
            else:
                yield event
    else:
        # Direct ReAct mode with progress
        progress_queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue()

        async def on_progress(hint: dict[str, object]) -> None:
            await progress_queue.put(hint)

        agent = OrchestratorAgent(
            db=db, llm=client, user_id=user_id, finance_tools=finance_tools
        )
        agent.set_progress_callback(on_progress)

        async def _run_agent():
            nonlocal cards, reply
            r, c = await agent.run(message)
            reply = r
            cards = c
            await progress_queue.put(None)

        agent_task = asyncio.create_task(_run_agent())

        while True:
            hint = await progress_queue.get()
            if hint is None:
                break
            yield hint
            save_checkpoint(
                db,
                user_id,
                sid,
                {
                    "mode": mode,
                    "message_key": hint.get("message_key"),
                    "message_params": hint.get("message_params"),
                },
            )

        await agent_task

    yield {
        "type": "done",
        "response": {
            "session_id": sid,
            "reply": reply,
            "cards": cards,
            "intent": intent,
            "partial": False,
            "llm_usage": usage_to_out(get_usage()),
        },
    }


async def _run_market_research_stream(
    llm: object,
    message: str,
    *,
    with_debate: bool = True,
) -> AsyncIterator[dict[str, object]]:
    """大盘深度投研：宏观/行业/技术/情绪，可选多空辩论 + 裁判。"""
    async for event in run_market_research_stream(
        message,
        llm=llm,  # type: ignore[arg-type]
        with_debate=with_debate,
    ):
        yield event


async def _run_stock_research_stream(
    llm: object,
    message: str,
    *,
    with_debate: bool = True,
    confirmed_symbol: str | None = None,
    confirmed_name: str | None = None,
) -> AsyncIterator[dict[str, object]]:
    """个股深度投研：四维 ReAct，可选多空辩论 + 裁判。"""
    yield status_event("status.identifying_stock")
    resolved = await resolve_message_stock(
        message,
        llm,  # type: ignore[arg-type]
        confirmed_symbol=confirmed_symbol,
        confirmed_name=confirmed_name,
    )
    if isinstance(resolved, StockLookupResult):
        card = stock_choice_card(message, resolved)
        yield {
            "type": "stock_choice",
            "message": resolved.message,
            "candidates": card["data"]["candidates"],
            "original_message": message,
        }
        yield {"type": "done", "cards": [card], "reply": resolved.message}
        return

    symbol = resolved.symbol
    _name = resolved.name

    cards: list[dict[str, object]] = []
    reply = ""
    async for event in run_research_stream(
        symbol,
        llm=llm,  # type: ignore[arg-type]
        with_debate=with_debate,
    ):
        if event.get("type") == "done":
            payload = event.get("result")
            if isinstance(payload, dict):
                report = ResearchReportOut.model_validate(payload)
                cards = [{"type": "research", "data": payload}]
                reply = report.summary
        else:
            yield event
    yield {"type": "done", "cards": cards, "reply": reply}


async def _run_industry_research_stream(
    db: Session,
    llm,
    user_id: int,
    sector: str,
    message: str,
    session_id: str,
    *,
    with_debate: bool = False,
) -> AsyncIterator[dict[str, object]]:
    save_checkpoint(
        db,
        user_id,
        session_id,
        {"mode": ComplexityResult.INDUSTRY_RESEARCH, "sector": sector, "message": message},
    )
    report: ResearchReportOut | None = None
    async for event in run_industry_research_stream(
        db,
        user_id,
        sector,
        message,
        llm,
        with_debate=with_debate,
    ):
        if event.get("type") == "status":
            save_checkpoint(
                db,
                user_id,
                session_id,
                {"mode": ComplexityResult.INDUSTRY_RESEARCH, "message": event.get("message", "")},
            )
        if event.get("type") == "done":
            raw = event.get("result")
            if isinstance(raw, dict):
                report = ResearchReportOut.model_validate(raw)
            continue
        yield event

    if report is None:
        yield {"type": "done", "cards": [], "reply": "板块投研暂时无法完成，请稍后重试。"}
        return

    cards: list[dict[str, object]] = [
        {"type": "research", "data": report.model_dump(mode="json")},
    ]
    yield {"type": "done", "cards": cards, "reply": report.summary}


async def _run_plan_execute_stream(
    db: Session,
    llm,
    message: str,
    user_id: int,
    session_id: str,
    *,
    finance_tools: bool = True,
) -> AsyncIterator[dict[str, object]]:
    """Stream plan-execute mode with progress."""
    yield status_event("status.planning")

    react_agent = OrchestratorAgent(
        db=db, llm=llm, user_id=user_id, finance_tools=finance_tools
    )

    async def tool_executor(name: str, args: dict) -> str:
        return await react_agent._execute_tool(name, args)

    agent = PlanExecuteAgent(
        llm=llm, tool_executor=tool_executor, finance_tools=finance_tools
    )

    # Use progress callback for real-time status
    progress_queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue()

    async def on_progress(hint: dict[str, object]) -> None:
        await progress_queue.put(hint)

    agent.set_progress_callback(on_progress)

    plan_cards: list[dict] = []
    plan_reply = ""

    async def _run():
        nonlocal plan_cards, plan_reply
        r, c = await agent.run(message)
        plan_reply = r
        plan_cards = c
        await progress_queue.put(None)

    task = asyncio.create_task(_run())

    # Yield progress events
    while True:
        try:
            hint = await asyncio.wait_for(progress_queue.get(), timeout=0.5)
            if hint is None:
                break
            yield hint
            save_checkpoint(
                db,
                user_id,
                session_id,
                {
                    "mode": ComplexityResult.PLAN_EXECUTE,
                    "message_key": hint.get("message_key"),
                    "message_params": hint.get("message_params"),
                },
            )
        except TimeoutError:
            pass

    await task
    merged_cards = _merge_plan_cards(plan_cards, react_agent.tool_cards())
    yield {"type": "done", "cards": merged_cards, "reply": plan_reply}


async def _upgrade_stock_research_route(
    message: str,
    llm: object,
    holdings: list[object],
    *,
    mode: str,
    debate_on: bool,
    execution_preference: str | None,
    confirmed_symbol: str | None,
    confirmed_name: str | None,
) -> tuple[str, str | None, str | None]:
    """Send holding/name stock analysis to streaming research instead of ReAct direct."""
    if execution_preference == "react":
        return mode, confirmed_symbol, confirmed_name
    if mode in (
        ComplexityResult.DEBATE,
        ComplexityResult.RESEARCH,
        ComplexityResult.MARKET_DEBATE,
        ComplexityResult.MARKET_RESEARCH,
        ComplexityResult.INDUSTRY_RESEARCH,
    ):
        return mode, confirmed_symbol, confirmed_name

    if not is_stock_analysis_intent(message):
        return mode, confirmed_symbol, confirmed_name

    holding = match_holding_in_message(message, holdings)
    if holding:
        upgraded = ComplexityResult.DEBATE if debate_on else ComplexityResult.RESEARCH
        return upgraded, holding.symbol, holding.name

    if mode != ComplexityResult.DIRECT:
        return mode, confirmed_symbol, confirmed_name

    resolved = await resolve_message_stock(
        message,
        llm,  # type: ignore[arg-type]
        confirmed_symbol=confirmed_symbol,
        confirmed_name=confirmed_name,
    )
    if isinstance(resolved, ResolvedStock):
        upgraded = ComplexityResult.DEBATE if debate_on else ComplexityResult.RESEARCH
        return upgraded, resolved.symbol, resolved.name

    return mode, confirmed_symbol, confirmed_name


def _merge_plan_cards(
    plan_cards: list[dict[str, object]],
    tool_cards: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Attach research/news/etc. cards produced by tools during Plan-Execute."""
    merged: list[dict[str, object]] = list(plan_cards)
    for card in tool_cards:
        ctype = card.get("type")
        if ctype == "research":
            merged = [c for c in merged if c.get("type") != "research"]
            merged.append(card)
        elif ctype in ("news", "financial", "debate", "market"):
            if not any(c.get("type") == ctype for c in merged):
                merged.append(card)
    return merged


def _save_conversation_async(
    db: Session, user_id: int, session_id: str, user_msg: str, reply: str,
) -> None:
    try:
        conv = db.query(Conversation).filter(
            Conversation.session_id == session_id,
        ).first()
        if conv is None:
            conv = Conversation(user_id=user_id, session_id=session_id, messages=[])
            db.add(conv)
        messages = list(conv.messages)
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": reply})
        conv.messages = messages[-20:]
        db.commit()
    except Exception:
        logger.warning(
            "Failed to save streaming conversation for session %s",
            session_id, exc_info=True,
        )
        try:
            db.rollback()
        except Exception:
            pass
