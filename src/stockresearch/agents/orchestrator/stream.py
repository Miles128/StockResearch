"""Streaming chat orchestrator — real-time progress + ReAct/Debate/PlanExecute."""

import asyncio
import uuid
from collections.abc import AsyncIterator

from sqlalchemy.orm import Session

from stockresearch.agents.market.research_stream import run_market_research_stream
from stockresearch.agents.industry.stream import run_industry_research_stream
from stockresearch.agents.orchestrator.complexity import (
    ANALYSIS_COMPLEX,
    ANALYSIS_SIMPLE,
    ComplexityResult,
    extract_industry_sector,
    is_risk_intent,
)
from stockresearch.agents.orchestrator.plan_execute import PlanExecuteAgent
from stockresearch.agents.orchestrator.react_agent import OrchestratorAgent
from stockresearch.agents.orchestrator.route_plan import (
    build_route_proposal,
    needs_execution_choice,
    resolve_mode_with_preference,
    route_choice_card,
)
from stockresearch.agents.research.stream import run_research_stream
from stockresearch.agents.risk.stream import run_risk_checkup_stream
from stockresearch.core.constants import INTENT_RESEARCH, INTENT_RISK
from stockresearch.core.schemas import ResearchReportOut
from stockresearch.core.schemas import CardPayload, ChatResponse, RiskCheckupOut
from stockresearch.db.models import Holding
from stockresearch.services.message_stock import resolve_message_stock, stock_choice_card
from stockresearch.services.stream_checkpoint import clear_checkpoint, save_checkpoint
from stockresearch.services.stock_lookup import StockLookupResult
from stockresearch.utils.disclaimer import strip_disclaimer
from stockresearch.utils.llm import LLMClient, get_llm_client
from stockresearch.utils.llm_usage import get_usage, reset_usage, usage_to_out


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

    yield {"type": "status", "message": "正在理解您的问题…"}

    msg = message.strip()
    is_risk = is_risk_intent(msg) and bool(holdings)

    debate_on = bool(enable_debate)

    cards: list[dict[str, object]] = []
    reply = ""
    partial = False
    intent = INTENT_RISK if is_risk else "chat"

    if is_risk:
        yield {"type": "status", "message": "已路由至「风控体检」…"}
        async for event in run_risk_checkup_stream(holdings, llm=client):
            if event.get("type") == "done":
                payload = event.get("result")
                if isinstance(payload, dict):
                    result = RiskCheckupOut.model_validate(payload)
                    cards = [{"type": "risk", "data": result.model_dump(mode="json")}]
                    reply = result.portfolio_summary
            else:
                yield event
    else:
        if needs_execution_choice(
            msg,
            analysis_mode=analysis_mode,
            execution_preference=execution_preference,
            confirmed_symbol=confirmed_symbol,
        ):
            proposal = build_route_proposal(msg, enable_debate=debate_on)
            card = route_choice_card(msg, proposal)
            yield {
                "type": "route_choice",
                "message": proposal.reason,
                "finance_related": proposal.finance_related,
                "preset_mode": proposal.preset_mode,
                "preset_label": proposal.preset_label,
                "options": [
                    {"id": o.id, "label": o.label, "description": o.description}
                    for o in proposal.options
                ],
                "original_message": msg,
            }
            cards = [card]
            reply = proposal.reason
        else:
            mode, finance_tools = resolve_mode_with_preference(
                msg,
                execution_preference,
                analysis_mode=analysis_mode,
                enable_debate=debate_on,
            )
            mode_labels = {
                ComplexityResult.DIRECT: "直接回答",
                ComplexityResult.RESEARCH: "个股多维投研",
                ComplexityResult.MARKET_RESEARCH: "大盘多维投研",
                ComplexityResult.DEBATE: "个股深度投研·多空辩论",
                ComplexityResult.MARKET_DEBATE: "大盘深度投研·多空辩论",
                ComplexityResult.PLAN_EXECUTE: "规划执行",
                ComplexityResult.INDUSTRY_RESEARCH: "行业深度研究",
            }
            debate_label = "多空辩论开" if debate_on else "多空辩论关"
            yield {
                "type": "status",
                "message": f"{debate_label} · {mode_labels.get(mode, mode)}",
            }

            if mode in (ComplexityResult.MARKET_DEBATE, ComplexityResult.MARKET_RESEARCH):
                intent = INTENT_RESEARCH
                async for event in _run_market_research_stream(
                    client,
                    msg,
                    with_debate=mode == ComplexityResult.MARKET_DEBATE,
                ):
                    if event.get("type") == "done":
                        payload = event.get("result")
                        if isinstance(payload, dict):
                            report = ResearchReportOut.model_validate(payload)
                            cards = [{"type": "research", "data": payload}]
                            reply = report.summary
                    else:
                        yield event
            elif mode in (ComplexityResult.DEBATE, ComplexityResult.RESEARCH):
                intent = INTENT_RESEARCH
                async for event in _run_stock_research_stream(
                    client,
                    msg,
                    with_debate=mode == ComplexityResult.DEBATE,
                    confirmed_symbol=confirmed_symbol,
                    confirmed_name=confirmed_name,
                ):
                    if event.get("type") == "done":
                        cards = event.get("cards", [])
                        reply = event.get("reply", "")
                    else:
                        yield event
            elif mode == ComplexityResult.PLAN_EXECUTE:
                async for event in _run_plan_execute_stream(
                    db, client, msg, user_id, sid, finance_tools=finance_tools
                ):
                    if event.get("type") == "done":
                        cards = event.get("cards", [])
                        reply = event.get("reply", "")
                    else:
                        yield event
            elif mode == ComplexityResult.INDUSTRY_RESEARCH:
                intent = INTENT_RESEARCH
                sectors = [h.sector for h in holdings]
                sector = extract_industry_sector(msg, sectors) or "行业"
                save_checkpoint(db, user_id, sid, {"mode": mode, "sector": sector, "message": msg})
                async for event in _run_industry_research_stream(
                    db, client, user_id, sector, msg, sid, with_debate=debate_on
                ):
                    if event.get("type") == "done":
                        cards = event.get("cards", [])
                        reply = event.get("reply", "")
                    else:
                        yield event
            else:
                # Direct ReAct mode with progress
                progress_queue: asyncio.Queue[str | None] = asyncio.Queue()

                async def on_progress(hint: str) -> None:
                    await progress_queue.put(hint)

                agent = OrchestratorAgent(
                    db=db, llm=client, user_id=user_id, finance_tools=finance_tools
                )
                agent.set_progress_callback(on_progress)

                async def _run_agent():
                    nonlocal reply, cards
                    r, c = await agent.run(message)
                    reply = r
                    cards = c
                    await progress_queue.put(None)

                agent_task = asyncio.create_task(_run_agent())

                while True:
                    hint = await progress_queue.get()
                    if hint is None:
                        break
                    yield {"type": "status", "message": hint}
                    save_checkpoint(db, user_id, sid, {"mode": mode, "message": hint})

                await agent_task

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
    yield {"type": "done", "response": response.model_dump(mode="json")}


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
    yield {"type": "status", "message": "正在识别股票…"}
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
    yield {"type": "status", "message": "正在制定研究计划…"}

    react_agent = OrchestratorAgent(
        db=db, llm=llm, user_id=user_id, finance_tools=finance_tools
    )

    async def tool_executor(name: str, args: dict) -> str:
        return await react_agent._execute_tool(name, args)

    agent = PlanExecuteAgent(
        llm=llm, tool_executor=tool_executor, finance_tools=finance_tools
    )

    # Use progress callback for real-time status
    progress_queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def on_progress(hint: str) -> None:
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
            yield {"type": "status", "message": hint}
            save_checkpoint(
                db,
                user_id,
                session_id,
                {"mode": ComplexityResult.PLAN_EXECUTE, "message": hint},
            )
        except TimeoutError:
            pass

    await task
    yield {"type": "done", "cards": plan_cards, "reply": plan_reply}
