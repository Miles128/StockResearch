"""Streaming chat orchestrator — real-time progress + ReAct/Debate/PlanExecute."""

import asyncio
import uuid
from collections.abc import AsyncIterator

from sqlalchemy.orm import Session

from stockresearch.agents.market.research_stream import run_market_research_stream
from stockresearch.agents.orchestrator.complexity import (
    ANALYSIS_COMPLEX,
    ANALYSIS_SIMPLE,
    ComplexityResult,
    is_risk_intent,
    needs_analysis_choice,
    resolve_execution_mode,
)
from stockresearch.agents.orchestrator.plan_execute import PlanExecuteAgent
from stockresearch.agents.orchestrator.react_agent import OrchestratorAgent
from stockresearch.agents.research.stream import run_research_stream
from stockresearch.agents.risk.stream import run_risk_checkup_stream
from stockresearch.core.constants import INTENT_RESEARCH, INTENT_RISK
from stockresearch.core.schemas import ResearchReportOut
from stockresearch.core.schemas import CardPayload, ChatResponse, RiskCheckupOut
from stockresearch.data.providers.market import QuoteProvider
from stockresearch.db.models import Holding
from stockresearch.utils.llm import LLMClient, get_llm_client


async def run_chat_stream(
    db: Session,
    user_id: int,
    message: str,
    session_id: str | None = None,
    llm: LLMClient | None = None,
    analysis_mode: str | None = None,
) -> AsyncIterator[dict[str, object]]:
    """Yield SSE events with real-time progress updates."""
    sid = session_id or str(uuid.uuid4())
    client = llm or get_llm_client()
    holdings = db.query(Holding).filter(Holding.user_id == user_id).all()

    yield {"type": "status", "message": "正在理解您的问题…"}

    msg = message.strip()
    is_risk = is_risk_intent(msg) and bool(holdings)

    if not is_risk and analysis_mode is None and needs_analysis_choice(msg, has_holdings=bool(holdings)):
        yield {
            "type": "analysis_choice",
            "message": "请选择分析深度",
            "query": msg,
            "options": [
                {"id": ANALYSIS_SIMPLE, "label": "简单分析", "hint": "快速直接回答"},
                {
                    "id": ANALYSIS_COMPLEX,
                    "label": "复杂分析",
                    "hint": "Multi-Agent 投研 / 多空辩论 / 规划执行",
                },
            ],
        }
        return

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
        mode = resolve_execution_mode(msg, analysis_mode)
        depth_label = (
            "简单分析"
            if analysis_mode == ANALYSIS_SIMPLE
            else "复杂分析"
            if analysis_mode == ANALYSIS_COMPLEX
            else "自动"
        )
        mode_labels = {
            ComplexityResult.DIRECT: "直接回答",
            ComplexityResult.DEBATE: "个股深度投研·多空辩论",
            ComplexityResult.MARKET_DEBATE: "大盘深度投研·多空辩论",
            ComplexityResult.PLAN_EXECUTE: "规划执行",
        }
        yield {
            "type": "status",
            "message": f"分析深度：{depth_label} · {mode_labels.get(mode, mode)}",
        }

        if mode == ComplexityResult.MARKET_DEBATE:
            intent = INTENT_RESEARCH
            async for event in _run_market_research_stream(client, msg):
                if event.get("type") == "done":
                    payload = event.get("result")
                    if isinstance(payload, dict):
                        report = ResearchReportOut.model_validate(payload)
                        cards = [{"type": "research", "data": payload}]
                        reply = report.summary
                else:
                    yield event
        elif mode == ComplexityResult.DEBATE:
            intent = INTENT_RESEARCH
            async for event in _run_stock_research_stream(client, msg):
                if event.get("type") == "done":
                    cards = event.get("cards", [])
                    reply = event.get("reply", "")
                else:
                    yield event
        elif mode == ComplexityResult.PLAN_EXECUTE:
            async for event in _run_plan_execute_stream(db, client, msg, user_id):
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

            agent = OrchestratorAgent(db=db, llm=client, user_id=user_id)
            agent.set_progress_callback(on_progress)

            # Run agent and progress consumer concurrently
            async def _run_agent():
                nonlocal reply, cards
                r, c = await agent.run(message)
                reply = r
                cards = c
                await progress_queue.put(None)  # signal done

            agent_task = asyncio.create_task(_run_agent())

            # Yield progress events while agent is running
            while True:
                hint = await progress_queue.get()
                if hint is None:
                    break
                yield {"type": "status", "message": hint}

            await agent_task

    if partial:
        reply += "\n\n（部分分析未完成）"

    response = ChatResponse(
        session_id=sid,
        reply=reply,
        cards=[CardPayload(type=c["type"], data=c["data"]) for c in cards],  # type: ignore[arg-type]
        intent=intent,
        partial=partial,
    )
    yield {"type": "done", "response": response.model_dump(mode="json")}


async def _run_market_research_stream(
    llm: object,
    message: str,
) -> AsyncIterator[dict[str, object]]:
    """大盘深度投研：宏观/行业/技术/情绪 + 多空辩论 + 裁判。"""
    async for event in run_market_research_stream(message, llm=llm):  # type: ignore[arg-type]
        yield event


async def _run_stock_research_stream(
    llm: object,
    message: str,
) -> AsyncIterator[dict[str, object]]:
    """个股深度投研：四维 ReAct + 多空辩论 + 裁判。"""
    yield {"type": "status", "message": "正在识别股票…"}
    symbol, _name = await _extract_symbol(message)
    if not symbol:
        yield {"type": "status", "message": "未识别到股票代码，请提供 6 位代码或常见股票名称"}
        yield {"type": "done", "cards": [], "reply": "请提供具体股票代码（如 600519）后再进行深度投研辩论。"}
        return

    cards: list[dict[str, object]] = []
    reply = ""
    async for event in run_research_stream(symbol, llm=llm):  # type: ignore[arg-type]
        if event.get("type") == "done":
            payload = event.get("result")
            if isinstance(payload, dict):
                report = ResearchReportOut.model_validate(payload)
                cards = [{"type": "research", "data": payload}]
                reply = report.summary
        else:
            yield event
    yield {"type": "done", "cards": cards, "reply": reply}


async def _run_plan_execute_stream(
    db: Session, llm, message: str, user_id: int
) -> AsyncIterator[dict[str, object]]:
    """Stream plan-execute mode with progress."""
    yield {"type": "status", "message": "正在制定研究计划…"}

    react_agent = OrchestratorAgent(db=db, llm=llm, user_id=user_id)

    async def tool_executor(name: str, args: dict) -> str:
        return await react_agent._execute_tool(name, args)

    agent = PlanExecuteAgent(llm=llm, tool_executor=tool_executor)

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
        except TimeoutError:
            pass

    await task
    yield {"type": "done", "cards": plan_cards, "reply": plan_reply}


async def _extract_symbol(message: str) -> tuple[str, str]:
    """Try to extract stock symbol from message."""
    import re

    match = re.search(r"\b(\d{6})\b", message)
    if match:
        symbol = match.group(1)
        try:
            provider = QuoteProvider()
            quote = await provider.get_quote(symbol)
            return symbol, quote.name
        except Exception:
            return symbol, symbol

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
