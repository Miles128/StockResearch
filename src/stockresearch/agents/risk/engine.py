"""Risk engine — rule-based thresholds + LLM-driven analysis + quantitative metrics."""

import asyncio
import logging

from stockresearch.agents.master_commentary.context import build_risk_context
from stockresearch.agents.master_commentary.stream import get_master_commentary
from stockresearch.agents.risk import messages as risk_msg
from stockresearch.agents.risk.metrics import (
    SINGLE_NAME_CONCENTRATION_LIMIT,
    SECTOR_CONCENTRATION_LIMIT,
    HoldingQuote,
    calculate_portfolio_metrics,
    calculate_var,
    closes_to_daily_returns,
    run_stress_presets,
)
from stockresearch.agents.voice import AGENT_VOICE
from stockresearch.core.constants import (
    SEVERITY_CRITICAL,
    SEVERITY_RED,
    SEVERITY_WARNING,
    SEVERITY_YELLOW,
)
from stockresearch.agents.master_commentary.registry import resolve_master_ids
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
from stockresearch.data.providers.market import QuoteProvider, TechnicalDataProvider
from stockresearch.db.models import Holding
from stockresearch.utils.llm import LLMClient, get_llm_client

logger = logging.getLogger(__name__)

_BLACK_SWAN_KEYWORDS = ("ST", "退市", "立案", "造假", "问询", "违规")

_RISK_LLM_BRIEF = f"{AGENT_VOICE} 客观平实，称呼「您」。"


async def _humanize(llm: LLMClient, alert: RiskAlertOut) -> str:
    system = (
        f"你是风控助手。{AGENT_VOICE} 用客气、平实的话提醒用户（称呼「您」）。"
        "不制造恐慌，不要建议买卖。"
    )
    user = f"规则 {alert.rule_id}：{alert.message}"
    return (await llm.complete(system, user)).strip()


async def _llm_market_assessment(llm: LLMClient, holdings: list[Holding]) -> str:
    if not holdings:
        return risk_msg.llm_no_holdings_market()
    holdings_desc = "\n".join(
        f"- {h.name}({h.symbol}) {h.sector} 成本{h.float_cost_price:.2f}" for h in holdings
    )
    system = f"你是 A 股风控分析师。{_RISK_LLM_BRIEF} 评估市场环境对组合的影响。不要建议买卖。"
    user = f"用户持仓：\n{holdings_desc}"
    return (await llm.complete(system, user)).strip()


async def _llm_correlation_analysis(llm: LLMClient, holdings: list[Holding]) -> str:
    if len(holdings) < 2:
        return risk_msg.llm_insufficient_correlation()
    holdings_desc = "\n".join(f"- {h.name}({h.symbol}) 行业:{h.sector}" for h in holdings)
    system = f"你是 A 股风控分析师。{_RISK_LLM_BRIEF} 分析持仓相关性风险。不要建议买卖。"
    user = f"用户持仓：\n{holdings_desc}"
    return (await llm.complete(system, user)).strip()


async def _llm_risk_narrative(
    llm: LLMClient, alerts: list[RiskAlertOut], holdings: list[Holding]
) -> str:
    if not alerts and not holdings:
        return risk_msg.llm_no_narrative_needed()
    alerts_desc = (
        "\n".join(f"- [{a.severity}] {a.message}" for a in alerts) if alerts else "未触发规则预警。"
    )
    holdings_desc = f"共 {len(holdings)} 只持仓" if holdings else "无持仓"
    system = f"你是 A 股风控分析师。{_RISK_LLM_BRIEF} 综合告警给出风险概述。不要建议买卖。"
    user = f"持仓概况：{holdings_desc}\n规则告警：\n{alerts_desc}"
    return (await llm.complete(system, user)).strip()


async def _llm_scenario_analysis(
    llm: LLMClient, holdings: list[Holding], alerts: list[RiskAlertOut]
) -> list[str]:
    if not holdings:
        return []
    holdings_desc = "\n".join(
        f"- {h.name}({h.symbol}) {h.sector} 成本{h.float_cost_price:.2f}" for h in holdings
    )
    alerts_desc = (
        "\n".join(f"- [{a.severity}] {a.message}" for a in alerts) if alerts else "无"
    )
    system = (
        f"你是 A 股风控分析师。{_RISK_LLM_BRIEF} "
        "列出最多2个风险情景，每行一个，格式：情景 | 影响。不要建议买卖。"
    )
    user = f"持仓：\n{holdings_desc}\n当前告警：\n{alerts_desc}"
    response = await llm.complete(system, user)
    scenarios = [line.strip() for line in response.strip().split("\n") if line.strip()]
    return scenarios[:2]


def _sector_concentration(holdings: list[Holding], quotes: list) -> tuple[float, str | None]:
    """Max sector weight by market value (aligned with PortfolioMetrics)."""
    if not holdings or not quotes:
        return 0.0, None
    sector_values: dict[str, float] = {}
    total = 0.0
    for h, q in zip(holdings, quotes, strict=True):
        value = float(q.price) * h.quantity
        sector_values[h.sector] = sector_values.get(h.sector, 0) + value
        total += value
    if total <= 0:
        return 0.0, None
    max_sector = max(sector_values, key=lambda sector: sector_values[sector])
    ratio = sector_values[max_sector] / total
    return ratio, max_sector


def _single_name_concentration(
    holdings: list[Holding], quotes: list
) -> tuple[float, str | None, str | None]:
    if not holdings or not quotes:
        return 0.0, None, None
    total = sum(float(q.price) * h.quantity for h, q in zip(holdings, quotes, strict=True))
    if total <= 0:
        return 0.0, None, None
    top_h, top_q = max(
        zip(holdings, quotes, strict=True),
        key=lambda pair: float(pair[1].price) * pair[0].quantity,
    )
    weight = (float(top_q.price) * top_h.quantity) / total
    return weight, top_h.symbol, top_h.name


def _parse_rule_alerts(holdings: list[Holding], quotes: list) -> list[RiskAlertOut]:
    """Shared rule-based alert parsing — used by both sync and streaming paths."""
    alerts: list[RiskAlertOut] = []
    for holding, quote in zip(holdings, quotes, strict=True):
        drawdown = (holding.float_cost_price - quote.price) / holding.float_cost_price
        if drawdown >= 0.15:
            alerts.append(
                RiskAlertOut(
                    rule_id="stop_loss_red",
                    severity=SEVERITY_RED,
                    symbol=holding.symbol,
                    message=risk_msg.alert_stop_loss_red(
                        holding.name, holding.symbol,
                        holding.float_cost_price, quote.price, drawdown,
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
                    message=risk_msg.alert_stop_loss_yellow(
                        holding.name, holding.symbol, drawdown,
                    ),
                    human_message="",
                )
            )
        if quote.change_pct <= -9.5:
            alerts.append(
                RiskAlertOut(
                    rule_id="black_swan",
                    severity=SEVERITY_CRITICAL,
                    symbol=holding.symbol,
                    message=risk_msg.alert_black_swan_drop(holding.name, quote.change_pct),
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
                        message=risk_msg.alert_black_swan_tag(holding.name, kw),
                        human_message="",
                    )
                )
                break
    ratio, sector = _sector_concentration(holdings, quotes)
    if ratio > SECTOR_CONCENTRATION_LIMIT and sector:
        alerts.append(
            RiskAlertOut(
                rule_id="concentration",
                severity=SEVERITY_WARNING,
                symbol=None,
                message=risk_msg.alert_concentration(sector, ratio),
                human_message="",
            )
        )
    name_w, name_sym, name_label = _single_name_concentration(holdings, quotes)
    if name_w > SINGLE_NAME_CONCENTRATION_LIMIT and name_sym and name_label:
        alerts.append(
            RiskAlertOut(
                rule_id="single_name_concentration",
                severity=SEVERITY_WARNING,
                symbol=name_sym,
                message=risk_msg.alert_single_name_concentration(name_label, name_sym, name_w),
                human_message="",
            )
        )
    return alerts


def _metrics_to_out(pm) -> PortfolioMetricsOut:
    return PortfolioMetricsOut(
        sharpe_ratio=round(pm.sharpe_ratio, 4),
        sortino_ratio=round(pm.sortino_ratio, 4),
        max_drawdown=round(pm.max_drawdown, 4),
        volatility=round(pm.volatility, 4),
        concentration_ratio=round(pm.concentration_ratio, 4),
        concentration_sector=pm.concentration_sector,
        individual_drawdowns=pm.individual_drawdowns,
        calmar_ratio=round(pm.calmar_ratio, 4),
        information_ratio=round(pm.information_ratio, 4),
        max_loss_1d=round(pm.max_loss_1d, 2),
        max_loss_1d_pct=round(pm.max_loss_1d_pct, 4),
        expected_loss=round(pm.expected_loss, 2),
        expected_loss_pct=round(pm.expected_loss_pct, 4),
        sector_weights=pm.sector_weights,
        top_holding_weight=round(pm.top_holding_weight, 4),
        top_holding_symbol=pm.top_holding_symbol,
        top_holding_name=pm.top_holding_name,
    )


async def _attach_daily_returns(holding_quotes: list[HoldingQuote]) -> None:
    """Best-effort fill of recent daily returns for VaR/vol (A-share closes)."""
    if not holding_quotes:
        return
    tech = TechnicalDataProvider()

    async def _one(hq: HoldingQuote) -> None:
        try:
            bars = await tech.get_kline_bars(hq.symbol, days=60)
            closes = [float(b["close"]) for b in bars]
            hq.daily_returns = closes_to_daily_returns(closes)[-40:]
        except Exception:
            logger.debug("daily_returns unavailable for %s", hq.symbol, exc_info=True)

    await asyncio.gather(*[_one(hq) for hq in holding_quotes])


async def run_risk_checkup(
    holdings: list[Holding],
    llm: LLMClient | None = None,
    *,
    enable_master_commentary: bool = False,
    mode_settings: ModeSettingsOut | None = None,
    master_ids: list[str] | None = None,
) -> RiskCheckupOut:
    client = llm or get_llm_client()
    quote_provider = QuoteProvider()

    quotes = await asyncio.gather(
        *[quote_provider.get_quote(holding.symbol) for holding in holdings]
    )

    alerts = _parse_rule_alerts(holdings, quotes)

    try:
        humanize_tasks = [_humanize(client, alert) for alert in alerts]
        analysis_tasks = [
            _llm_market_assessment(client, holdings),
            _llm_correlation_analysis(client, holdings),
            _llm_risk_narrative(client, alerts, holdings),
            _llm_scenario_analysis(client, holdings, alerts),
        ]

        humanize_results = await asyncio.gather(*humanize_tasks, return_exceptions=True)
        for alert, result in zip(alerts, humanize_results):
            alert.human_message = result if isinstance(result, str) else alert.message

        analysis_results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
        market_assessment = (
            analysis_results[0]
            if isinstance(analysis_results[0], str)
            else risk_msg.llm_unavailable_market()
        )
        correlation_analysis = (
            analysis_results[1]
            if isinstance(analysis_results[1], str)
            else risk_msg.llm_unavailable_correlation()
        )
        risk_narrative = (
            analysis_results[2]
            if isinstance(analysis_results[2], str)
            else risk_msg.llm_unavailable_narrative()
        )
        scenario_analysis = analysis_results[3] if isinstance(analysis_results[3], list) else []
        llm_analysis = LLMRiskAnalysis(
            market_assessment=market_assessment,
            correlation_analysis=correlation_analysis,
            risk_narrative=risk_narrative,
            scenario_analysis=scenario_analysis,
        )
    except Exception:
        logger.warning("LLM risk analysis failed, returning rule-based results only")
        for alert in alerts:
            if not alert.human_message:
                alert.human_message = alert.message
        llm_analysis = None

    if not holdings:
        summary = risk_msg.portfolio_summary_no_holdings()
    elif not alerts:
        summary = risk_msg.portfolio_summary_all_clear(len(holdings))
    else:
        summary = risk_msg.portfolio_summary_with_alerts(len(alerts))

    # ── 量化风险指标 ──
    metrics_out: PortfolioMetricsOut | None = None
    var_out: VaRResultOut | None = None
    stress_out: list[StressResultOut] = []
    if holdings:
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
                StressResultOut.model_validate(item)
                for item in run_stress_presets(holding_quotes)
            ]
        except Exception:
            logger.warning("Quantitative metrics calculation failed", exc_info=True)

    result = RiskCheckupOut(
        alerts=alerts,
        portfolio_summary=summary,
        llm_analysis=llm_analysis,
        metrics=metrics_out,
        var_result=var_out,
        stress_results=stress_out,
    )
    if enable_master_commentary and mode_settings is not None:
        masters = master_ids or resolve_master_ids(mode_settings)
        commentary_context = build_risk_context(result)
        commentary = await get_master_commentary(
            client,
            subject="组合风险分析",
            context=commentary_context,
            settings=mode_settings,
            masters=masters,
        )
        result.master_commentary = [
            MasterCommentaryItem.model_validate(item) for item in commentary
        ]
    return result
