"""Streaming multi-agent risk checkup — parallel analysts + bull/bear debate + judge."""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from stockresearch.agents.master_commentary.context import build_risk_context
from stockresearch.agents.master_commentary.registry import resolve_master_ids
from stockresearch.agents.master_commentary.stream import stream_master_commentary
from stockresearch.agents.research.debate import (
    iter_triangular_debate_events,
    triangular_transcript,
)
from stockresearch.agents.risk import messages as risk_msg
from stockresearch.agents.risk.engine import (
    _attach_daily_returns,
    _llm_correlation_analysis,
    _llm_market_assessment,
    _llm_scenario_analysis,
    _metrics_to_out,
    _parse_rule_alerts,
    run_risk_checkup,
)
from stockresearch.agents.risk.judge import (
    JudgeVerdict,
    format_judge_display,
    parse_judge,
    portfolio_summary_text,
)
from stockresearch.agents.risk.metrics import (
    HoldingQuote,
    calculate_portfolio_metrics,
    calculate_var,
    run_stress_presets,
)
from stockresearch.agents.stream_typewriter import (
    AgentStreamItem,
    iter_agent_done_stream,
    iter_llm_stream_events,
    iter_merged_agent_streams_from_tasks,
)
from stockresearch.agents.voice import JUDGE_VOICE
from stockresearch.core.schemas import (
    LLMRiskAnalysis,
    MasterCommentaryItem,
    ModeSettingsOut,
    PortfolioMetricsOut,
    RiskAlertOut,
    RiskCheckupOut,
    StressResultOut,
    VaRResultOut,
)
from stockresearch.data.providers.market import QuoteProvider
from stockresearch.db.models import Holding
from stockresearch.i18n.status_events import status_event
from stockresearch.services.compliance_language import (
    normalize_position_action,
    scrub_forbidden_position_language,
)
from stockresearch.utils.llm import LLMClient, get_llm_client

logger = logging.getLogger(__name__)

# Risk tab: one debate round keeps latency acceptable (full research still uses DEBATE_ROUNDS).
_RISK_DEBATE_ROUNDS = 1

_JUDGE_RISK_SYSTEM = f"""你是风控裁判 Agent。{JUDGE_VOICE} 只输出 JSON，禁止 markdown。
{{
  "analysis_process": "分3-5步说明您如何从告警、分析与辩论证据推到结论，每步一句",
  "risk_level": "低|中|高",
  "position_action": "组合仓位倾向：仓位偏高|仓位偏低|仓位适中|建议控制仓位",
  "holding_actions": [
    {{"symbol":"600519","name":"贵州茅台","action":"仓位偏高|仓位偏低|仓位适中|建议控制仓位|暂不调整","reason":"针对该股1-2句依据","priority":"高|中|低"}}
  ],
  "summary": "组合综合结论2-3句",
  "reason": "组合层面核心理由2句",
  "divergence": "分歧大|分歧中等|分歧小"
}}
硬性要求：holding_actions 必须覆盖每一只持仓，条数与持仓只数一致；
每只都要写清 action 与 reason。priority=高 表示最需优先处理。"""


def _parse_judge(raw: str, alerts: list[RiskAlertOut], holdings: list[Holding]) -> JudgeVerdict:
    return parse_judge(raw, alerts, holdings)


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
        cp = holding.float_cost_price
        if cp:
            drawdown = (cp - quote.price) / cp
        else:
            drawdown = 0.0
        stock_alerts = alerts_by_symbol.get(holding.symbol, [])
        alert_text = "；".join(a.message for a in stock_alerts) if stock_alerts else "无个股告警"
        lines.append(
            f"- {holding.name}({holding.symbol}) 行业{holding.sector} "
            f"现价{quote.price:.2f} 成本{cp:.2f} 回撤{drawdown:.1%} · {alert_text}"
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


async def _compute_quant_metrics(
    holdings: list[Holding],
    quotes: list,
) -> tuple[PortfolioMetricsOut | None, VaRResultOut | None, list[StressResultOut]]:
    if not holdings:
        return None, None, []
    try:
        holding_quotes = [
            HoldingQuote(
                symbol=h.symbol,
                name=h.name,
                cost_price=h.float_cost_price,
                current_price=q.price,
                quantity=h.quantity,
                sector=h.sector,
                buy_date=str(h.buy_date) if h.buy_date else None,
            )
            for h, q in zip(holdings, quotes, strict=True)
        ]
        await _attach_daily_returns(holding_quotes)
        pm = calculate_portfolio_metrics(holding_quotes)
        metrics_out = _metrics_to_out(pm)
        vr = calculate_var(holding_quotes)
        var_out = VaRResultOut(
            confidence_level=vr.confidence_level,
            time_horizon_days=vr.time_horizon_days,
            var_value=round(vr.var_value, 2),
            var_pct=round(vr.var_pct, 4),
            method=vr.method,
            holdings_var=vr.holdings_var,
            cvar_value=round(vr.cvar_value, 2),
            cvar_pct=round(vr.cvar_pct, 4),
        )
        stress_out = [
            StressResultOut.model_validate(item) for item in run_stress_presets(holding_quotes)
        ]
        return metrics_out, var_out, stress_out
    except Exception:
        logger.warning("Quantitative metrics calculation failed", exc_info=True)
        return None, None, []


async def run_risk_checkup_stream(
    holdings: list[Holding],
    llm: LLMClient | None = None,
    *,
    enable_master_commentary: bool = False,
    enable_llm_analysis: bool = True,
    mode_settings: ModeSettingsOut | None = None,
    master_ids: list[str] | None = None,
) -> AsyncIterator[dict[str, object]]:
    """Stream risk checkup.

    PRD §四: 规则引擎 + 可选 LLM 解读。`enable_llm_analysis=False` 时跳过
    parallel LLM agents / 三角辩论 / Research Manager / Judge,直接返回
    规则告警 + 量化指标。`enable_llm_analysis` 同时控制 master_commentary
    (后者还需 `enable_master_commentary=True`)。
    """
    client = llm or get_llm_client()

    yield status_event("status.risk.analysis")

    yield {
        "type": "agent_start",
        "agent_id": "rules",
        "agent_name": "规则引擎",
        "role": "rules",
    }
    quote_provider = QuoteProvider()
    quote_map = await quote_provider.get_quotes([h.symbol for h in holdings]) if holdings else {}
    quotes = [quote_map[h.symbol] for h in holdings if h.symbol in quote_map]
    if holdings and len(quotes) != len(holdings):
        missing = [h.symbol for h in holdings if h.symbol not in quote_map]
        logger.warning("Risk checkup missing quotes for: %s", ",".join(missing))

    alerts = _parse_rule_alerts(holdings, quotes)
    for alert in alerts:
        alert.human_message = alert.message
    rules_summary = risk_msg.rules_scan_summary(len(holdings), len(alerts))
    async for event in iter_agent_done_stream(
        agent_id="rules",
        agent_name="规则引擎",
        role="rules",
        content=rules_summary,
    ):
        yield event

    metrics_out, var_out, stress_out = await _compute_quant_metrics(holdings, quotes)
    if holdings and (metrics_out or var_out or alerts or stress_out):
        yield {
            "type": "risk_snapshot",
            "result": RiskCheckupOut(
                alerts=alerts,
                portfolio_summary="",
                llm_analysis=None,
                metrics=metrics_out,
                var_result=var_out,
                stress_results=stress_out,
            ).model_dump(mode="json"),
        }

    if not holdings:
        empty = await run_risk_checkup(
            holdings, llm=client, enable_llm_analysis=enable_llm_analysis
        )
        yield {"type": "done", "result": empty.model_dump(mode="json")}
        return

    # PRD §四 可选 LLM：关闭时跳过 parallel agents / debate / manager / judge
    if not enable_llm_analysis:
        if not alerts:
            summary = risk_msg.portfolio_summary_all_clear(len(holdings))
        else:
            summary = risk_msg.portfolio_summary_with_alerts(len(alerts))
        result = RiskCheckupOut(
            alerts=alerts,
            portfolio_summary=summary,
            llm_analysis=None,
            metrics=metrics_out,
            var_result=var_out,
            stress_results=stress_out,
        )
        yield {"type": "done", "result": result.model_dump(mode="json")}
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
        rounds=_RISK_DEBATE_ROUNDS,
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

    yield status_event("status.risk.manager")
    yield {
        "type": "agent_start",
        "agent_id": "research_manager",
        "agent_name": "Research Manager",
        "role": "manager",
    }
    manager_summary = ""
    async for event in iter_llm_stream_events(
        stream_id="research_manager",
        agent_id="research_manager",
        agent_name="Research Manager",
        role="manager",
        llm=client,
        system=f"你是风控 Research Manager。{JUDGE_VOICE} 用3-4句综合三方观点，说明最大分歧与您的倾向。",
        user=f"{debate_context}\n{triangular_transcript(debate_lines)}",
    ):
        yield event
        if event.get("type") == "agent_done":
            manager_summary = str(event.get("content", "")).strip()
    yield {"type": "manager", "content": manager_summary}

    yield status_event("status.risk.judge")
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
    judge_raw = ""
    async for event in iter_llm_stream_events(
        stream_id="judge",
        agent_id="judge",
        agent_name="裁判",
        role="judge",
        llm=client,
        system=_JUDGE_RISK_SYSTEM,
        user=judge_user,
    ):
        yield event
        if event.get("type") == "agent_done":
            judge_raw = str(event.get("content", ""))
    verdict = _parse_judge(judge_raw, alerts, holdings)
    judge_display = scrub_forbidden_position_language(format_judge_display(verdict))
    holding_actions_payload = [
        item.model_copy(
            update={"action": normalize_position_action(item.action, portfolio=False)}
        ).model_dump()
        for item in verdict.holding_actions
    ]
    yield {
        "type": "judge",
        "risk_level": verdict.risk_level,
        "position_action": normalize_position_action(verdict.position_action, portfolio=True),
        "summary": scrub_forbidden_position_language(verdict.summary),
        "reason": scrub_forbidden_position_language(verdict.reason),
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

    # Metrics already computed for risk_snapshot; reuse if still valid.
    if metrics_out is None and var_out is None:
        metrics_out, var_out, stress_out = await _compute_quant_metrics(holdings, quotes)

    result = RiskCheckupOut(
        alerts=alerts,
        portfolio_summary=summary,
        llm_analysis=llm_analysis,
        metrics=metrics_out,
        var_result=var_out,
        stress_results=stress_out,
    )

    if enable_llm_analysis and enable_master_commentary and mode_settings is not None:
        masters = master_ids or resolve_master_ids(mode_settings)
        commentary_context = build_risk_context(result)
        commentary: list[dict[str, Any]] = []
        async for mc_event in stream_master_commentary(
            client,
            subject="组合风险分析",
            context=commentary_context,
            settings=mode_settings,
            masters=masters,
        ):
            yield mc_event
            if mc_event.get("type") == "master_commentary" and isinstance(
                mc_event.get("commentary"), list
            ):
                commentary = mc_event["commentary"]
        result.master_commentary = [
            MasterCommentaryItem.model_validate(item) for item in commentary
        ]

    yield {"type": "done", "result": result.model_dump(mode="json")}
