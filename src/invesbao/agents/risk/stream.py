"""Streaming multi-agent risk checkup — parallel analysts + bull/bear debate + judge."""

import asyncio
import logging
from collections.abc import AsyncIterator

from invesbao.agents.research.debate import iter_triangular_debate_events, triangular_transcript
from invesbao.agents.risk.engine import (
    _humanize,
    _llm_correlation_analysis,
    _llm_market_assessment,
    _llm_scenario_analysis,
    _sector_concentration,
    run_risk_checkup,
)
from invesbao.agents.risk.judge import (
    JudgeVerdict,
    format_judge_display,
    parse_judge,
    portfolio_summary_text,
)
from invesbao.agents.stream_typewriter import (
    AgentStreamItem,
    iter_agent_done_stream,
    iter_merged_agent_streams_from_tasks,
    iter_queue_merged_events,
    iter_text_deltas,
    pump_agent_done_stream,
)
from invesbao.agents.voice import DEBATE_ROUNDS, JUDGE_VOICE
from invesbao.core.constants import (
    SEVERITY_CRITICAL,
    SEVERITY_RED,
    SEVERITY_WARNING,
    SEVERITY_YELLOW,
)
from invesbao.core.schemas import LLMRiskAnalysis, RiskAlertOut, RiskCheckupOut
from invesbao.data.providers.market import QuoteProvider
from invesbao.db.models import Holding
from invesbao.utils.llm import LLMClient, get_llm_client

logger = logging.getLogger(__name__)

_BLACK_SWAN_KEYWORDS = ("ST", "退市", "立案", "造假", "问询", "违规")
_JUDGE_RISK_SYSTEM = f"""你是风控裁判 Agent。{JUDGE_VOICE} 只输出 JSON，禁止 markdown。
{{
  "analysis_process": "分3-5步说明您如何从告警、分析与辩论证据推到结论，每步一句",
  "risk_level": "低|中|高",
  "position_action": "组合整体倾向：加仓|减仓|持有观望",
  "holding_actions": [
    {{"symbol":"600519","name":"贵州茅台","action":"减仓|加仓|持有观望|暂不调整","reason":"针对该股1-2句依据","priority":"高|中|低"}}
  ],
  "summary": "组合综合结论2-3句",
  "reason": "组合层面核心理由2句",
  "divergence": "分歧大|分歧中等|分歧小"
}}
硬性要求：holding_actions 必须覆盖每一只持仓，条数与持仓只数一致；
每只都要写清 action 与 reason。priority=高 表示最需优先处理。"""


def _parse_judge(raw: str, alerts: list[RiskAlertOut], holdings: list[Holding]) -> JudgeVerdict:
    return parse_judge(raw, alerts, holdings)


def _parse_rule_alerts(holdings: list[Holding], quotes: list) -> list[RiskAlertOut]:
    alerts: list[RiskAlertOut] = []
    for holding, quote in zip(holdings, quotes, strict=True):
        drawdown = (holding.cost_price - quote.price) / holding.cost_price
        if drawdown >= 0.15:
            alerts.append(
                RiskAlertOut(
                    rule_id="stop_loss_red",
                    severity=SEVERITY_RED,
                    symbol=holding.symbol,
                    message=(
                        f"{holding.name}({holding.symbol}) 亏损 {drawdown:.0%}，触发红色止损预警。"
                    ),
                    human_message="",
                )
            )
        elif drawdown >= 0.08:
            alerts.append(
                RiskAlertOut(
                    rule_id="stop_loss_yellow",
                    severity=SEVERITY_YELLOW,
                    symbol=holding.symbol,
                    message=f"{holding.name}({holding.symbol}) 回撤 {drawdown:.0%}。",
                    human_message="",
                )
            )
        if quote.change_pct <= -9.5:
            alerts.append(
                RiskAlertOut(
                    rule_id="black_swan",
                    severity=SEVERITY_CRITICAL,
                    symbol=holding.symbol,
                    message=f"{holding.name} 今日大跌 {quote.change_pct}%。",
                    human_message="",
                )
            )
        for kw in _BLACK_SWAN_KEYWORDS:
            if kw in holding.name:
                alerts.append(
                    RiskAlertOut(
                        rule_id="black_swan",
                        severity=SEVERITY_CRITICAL,
                        symbol=holding.symbol,
                        message=f"{holding.name} 存在 {kw} 相关风险标签。",
                        human_message="",
                    )
                )
                break
    ratio, sector = _sector_concentration(holdings)
    if ratio > 0.40 and sector:
        alerts.append(
            RiskAlertOut(
                rule_id="concentration",
                severity=SEVERITY_WARNING,
                symbol=None,
                message=f"行业集中度偏高：{sector} 占仓位 {ratio:.0%}。",
                human_message="",
            )
        )
    return alerts


def _holdings_detail_block(
    holdings: list[Holding],
    quotes: list,
    alerts: list[RiskAlertOut],
) -> str:
    alerts_by_symbol: dict[str, list[RiskAlertOut]] = {}
    portfolio_alerts: list[RiskAlertOut] = []
    for alert in alerts:
        if alert.symbol:
            alerts_by_symbol.setdefault(alert.symbol, []).append(alert)
        else:
            portfolio_alerts.append(alert)

    lines: list[str] = []
    for holding, quote in zip(holdings, quotes, strict=True):
        if holding.cost_price:
            drawdown = (holding.cost_price - quote.price) / holding.cost_price
        else:
            drawdown = 0.0
        stock_alerts = alerts_by_symbol.get(holding.symbol, [])
        alert_text = "；".join(a.message for a in stock_alerts) if stock_alerts else "无个股告警"
        lines.append(
            f"- {holding.name}({holding.symbol}) 行业{holding.sector} "
            f"现价{quote.price:.2f} 成本{holding.cost_price:.2f} 回撤{drawdown:.1%} · {alert_text}"
        )
    if portfolio_alerts:
        lines.append("组合层面：" + "；".join(a.message for a in portfolio_alerts))
    return "\n".join(lines)


def _context_block(
    holdings: list[Holding],
    quotes: list,
    alerts: list[RiskAlertOut],
) -> str:
    detail = _holdings_detail_block(holdings, quotes, alerts)
    return f"持仓明细（共 {len(holdings)} 只）：\n{detail}"


async def run_risk_checkup_stream(
    holdings: list[Holding],
    llm: LLMClient | None = None,
) -> AsyncIterator[dict[str, object]]:
    client = llm or get_llm_client()

    yield {"type": "status", "message": "多 Agent 风控分析中…"}

    yield {
        "type": "agent_start",
        "agent_id": "rules",
        "agent_name": "规则引擎",
        "role": "rules",
    }
    quote_provider = QuoteProvider()
    quotes = (
        await asyncio.gather(*[quote_provider.get_quote(h.symbol) for h in holdings])
        if holdings
        else []
    )
    alerts = _parse_rule_alerts(holdings, quotes)
    rules_summary = (
        f"扫描 {len(holdings)} 只，触发 {len(alerts)} 条告警。"
        if holdings
        else "暂无持仓。"
    )
    async for event in iter_agent_done_stream(
        agent_id="rules",
        agent_name="规则引擎",
        role="rules",
        content=rules_summary,
    ):
        yield event

    if not holdings:
        empty = await run_risk_checkup(holdings, llm=client)
        yield {"type": "done", "result": empty.model_dump(mode="json")}
        return

    context = _context_block(holdings, quotes, alerts)
    parallel_agents: list[tuple[str, str, object]] = [
        ("market", "市场环境", _llm_market_assessment),
        ("correlation", "相关性", _llm_correlation_analysis),
        (
            "scenario",
            "情景推演",
            lambda c, h: _llm_scenario_analysis(c, h, alerts),
        ),
    ]

    for agent_id, agent_name, _ in parallel_agents:
        yield {
            "type": "agent_start",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "role": "analyst",
        }

    async def run_agent(
        agent_id: str,
        agent_name: str,
        fn: object,
    ) -> AgentStreamItem:
        if agent_id == "scenario":
            content = await fn(client, holdings)  # type: ignore[operator]
            text = "；".join(content) if isinstance(content, list) else str(content)
        else:
            text = await fn(client, holdings)  # type: ignore[operator]
        return AgentStreamItem(
            agent_id=agent_id,
            agent_name=agent_name,
            role="analyst",
            content=text.strip(),
        )

    tasks = [
        asyncio.create_task(run_agent(agent_id, agent_name, fn))
        for agent_id, agent_name, fn in parallel_agents
    ]
    analysis: dict[str, str] = {}
    async for event in iter_merged_agent_streams_from_tasks(tasks):
        if event.get("type") == "agent_done" and event.get("agent_id"):
            analysis[str(event["agent_id"])] = str(event.get("content", ""))
        yield event

    debate_context = (
        f"{context} | 市场：{analysis['market']} | "
        f"相关：{analysis['correlation']} | 情景：{analysis['scenario']}"
    )

    debate_lines: list[str] = []
    async for event in iter_triangular_debate_events(
        client,
        debate_context,
        rounds=DEBATE_ROUNDS,
    ):
        yield event
        if event.get("type") == "debate_round":
            round_num = event.get("round")
            if isinstance(round_num, int):
                debate_lines.append(
                    f"第{round_num}轮激进：{event.get('aggressive', '')}\n"
                    f"第{round_num}轮中性：{event.get('neutral_view', '')}\n"
                    f"第{round_num}轮审慎：{event.get('conservative', '')}"
                )

    yield {"type": "status", "message": "Research Manager 综合风控意见…"}
    manager_raw = await client.complete(
        f"你是风控 Research Manager。{JUDGE_VOICE} 用3-4句综合三方观点，说明最大分歧与您的倾向。",
        f"{debate_context}\n{triangular_transcript(debate_lines)}",
    )
    manager_summary = manager_raw.strip()
    yield {
        "type": "agent_start",
        "agent_id": "research_manager",
        "agent_name": "Research Manager",
        "role": "manager",
    }
    async for delta_event in iter_text_deltas("research_manager", manager_summary):
        yield delta_event
    yield {
        "type": "agent_done",
        "agent_id": "research_manager",
        "agent_name": "Research Manager",
        "role": "manager",
        "content": manager_summary,
    }

    yield {"type": "status", "message": "裁判逐股研判并汇总结论…"}
    yield {
        "type": "agent_start",
        "agent_id": "judge",
        "agent_name": "裁判",
        "role": "judge",
    }
    judge_user = (
        f"{context}\n\n{debate_context}\n"
        f"{triangular_transcript(debate_lines)}\nResearch Manager：{manager_summary}\n\n"
        f"请对以上 {len(holdings)} 只持仓逐只给出 holding_actions，不可遗漏。"
    )
    judge_raw = await client.complete(_JUDGE_RISK_SYSTEM, judge_user)
    verdict = _parse_judge(judge_raw, alerts, holdings)
    judge_display = format_judge_display(verdict)
    async for delta_event in iter_text_deltas("judge", judge_display):
        yield delta_event
    holding_actions_payload = [item.model_dump() for item in verdict.holding_actions]
    yield {
        "type": "judge",
        "risk_level": verdict.risk_level,
        "position_action": verdict.position_action,
        "summary": verdict.summary,
        "reason": verdict.reason,
        "divergence": verdict.divergence,
        "analysis_process": verdict.analysis_process,
        "holding_actions": holding_actions_payload,
        "verdict": verdict.risk_level,
        "content": verdict.summary,
    }
    yield {
        "type": "agent_done",
        "agent_id": "judge",
        "agent_name": "裁判",
        "role": "judge",
        "content": judge_display,
    }

    try:
        humanize_results = await asyncio.gather(*[_humanize(client, a) for a in alerts])
        for alert, human_msg in zip(alerts, humanize_results, strict=True):
            alert.human_message = human_msg.strip() or alert.message
    except Exception:
        logger.warning("Humanize alerts failed")
        for alert in alerts:
            alert.human_message = alert.message

    llm_analysis = LLMRiskAnalysis(
        market_assessment=analysis["market"],
        correlation_analysis=analysis["correlation"],
        risk_narrative=verdict.summary,
        scenario_analysis=[analysis["scenario"]],
        risk_level=verdict.risk_level,
        position_action=verdict.position_action,
        analysis_process=verdict.analysis_process,
        holding_actions=list(verdict.holding_actions),
    )
    summary = portfolio_summary_text(verdict)
    result = RiskCheckupOut(
        alerts=alerts,
        portfolio_summary=summary,
        llm_analysis=llm_analysis,
    )
    yield {"type": "done", "result": result.model_dump(mode="json")}
