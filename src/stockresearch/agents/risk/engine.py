"""Risk engine — rule-based thresholds + LLM-driven analysis + quantitative metrics."""

import asyncio
import logging

from stockresearch.agents.risk.metrics import (
    HoldingQuote,
    calculate_portfolio_metrics,
    calculate_var,
)
from stockresearch.agents.voice import AGENT_VOICE
from stockresearch.core.constants import (
    SEVERITY_CRITICAL,
    SEVERITY_RED,
    SEVERITY_WARNING,
    SEVERITY_YELLOW,
)
from stockresearch.core.schemas import (
    LLMRiskAnalysis,
    PortfolioMetricsOut,
    RiskAlertOut,
    RiskCheckupOut,
    VaRResultOut,
)
from stockresearch.data.providers.market import QuoteProvider
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
        return "无持仓，无法评估市场环境。"
    holdings_desc = "\n".join(
        f"- {h.name}({h.symbol}) {h.sector} 成本{h.cost_price}" for h in holdings
    )
    system = f"你是 A 股风控分析师。{_RISK_LLM_BRIEF} 评估市场环境对组合的影响。不要建议买卖。"
    user = f"用户持仓：\n{holdings_desc}"
    return (await llm.complete(system, user)).strip()


async def _llm_correlation_analysis(llm: LLMClient, holdings: list[Holding]) -> str:
    if len(holdings) < 2:
        return "持仓不足两只，无需分析相关性。"
    holdings_desc = "\n".join(f"- {h.name}({h.symbol}) 行业:{h.sector}" for h in holdings)
    system = f"你是 A 股风控分析师。{_RISK_LLM_BRIEF} 分析持仓相关性风险。不要建议买卖。"
    user = f"用户持仓：\n{holdings_desc}"
    return (await llm.complete(system, user)).strip()


async def _llm_risk_narrative(
    llm: LLMClient, alerts: list[RiskAlertOut], holdings: list[Holding]
) -> str:
    if not alerts and not holdings:
        return "暂无持仓，无需生成风险叙述。"
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
        f"- {h.name}({h.symbol}) {h.sector} 成本{h.cost_price}" for h in holdings
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


def _sector_concentration(holdings: list[Holding]) -> tuple[float, str | None]:
    if not holdings:
        return 0.0, None
    sector_values: dict[str, float] = {}
    total = 0.0
    for h in holdings:
        value = h.cost_price * h.quantity
        sector_values[h.sector] = sector_values.get(h.sector, 0) + value
        total += value
    if total <= 0:
        return 0.0, None
    max_sector = max(sector_values, key=lambda sector: sector_values[sector])
    ratio = sector_values[max_sector] / total
    return ratio, max_sector


async def run_risk_checkup(
    holdings: list[Holding],
    llm: LLMClient | None = None,
) -> RiskCheckupOut:
    client = llm or get_llm_client()
    quote_provider = QuoteProvider()
    alerts: list[RiskAlertOut] = []

    quotes = await asyncio.gather(
        *[quote_provider.get_quote(holding.symbol) for holding in holdings]
    )

    for holding, quote in zip(holdings, quotes, strict=True):
        drawdown = (holding.cost_price - quote.price) / holding.cost_price

        if drawdown >= 0.15:
            msg = (
                f"{holding.name}({holding.symbol}) 从成本 {holding.cost_price:.2f} "
                f"回撤至 {quote.price:.2f}，亏损 {drawdown:.0%}，触发红色止损预警。"
            )
            alerts.append(
                RiskAlertOut(
                    rule_id="stop_loss_red",
                    severity=SEVERITY_RED,
                    symbol=holding.symbol,
                    message=msg,
                    human_message="",
                )
            )
        elif drawdown >= 0.08:
            msg = (
                f"{holding.name}({holding.symbol}) 回撤 {drawdown:.0%}，"
                f"接近你设定的止损关注区间（8%）。"
            )
            alerts.append(
                RiskAlertOut(
                    rule_id="stop_loss_yellow",
                    severity=SEVERITY_YELLOW,
                    symbol=holding.symbol,
                    message=msg,
                    human_message="",
                )
            )

        if quote.change_pct <= -9.5:
            msg = f"{holding.name} 今日大跌 {quote.change_pct}%，请关注是否有重大利空。"
            alerts.append(
                RiskAlertOut(
                    rule_id="black_swan",
                    severity=SEVERITY_CRITICAL,
                    symbol=holding.symbol,
                    message=msg,
                    human_message="",
                )
            )

        for kw in _BLACK_SWAN_KEYWORDS:
            if kw in holding.name:
                msg = f"{holding.name} 存在 {kw} 相关风险标签，请重点关注公告。"
                alerts.append(
                    RiskAlertOut(
                        rule_id="black_swan",
                        severity=SEVERITY_CRITICAL,
                        symbol=holding.symbol,
                        message=msg,
                        human_message="",
                    )
                )
                break

    ratio, sector = _sector_concentration(holdings)
    if ratio > 0.40 and sector:
        msg = f"行业集中度偏高：{sector} 占仓位 {ratio:.0%}，超过 40% 阈值。"
        alerts.append(
            RiskAlertOut(
                rule_id="concentration",
                severity=SEVERITY_WARNING,
                symbol=None,
                message=msg,
                human_message="",
            )
        )

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
            else "市场环境评估暂时不可用。"
        )
        correlation_analysis = (
            analysis_results[1]
            if isinstance(analysis_results[1], str)
            else "相关性分析暂时不可用。"
        )
        risk_narrative = (
            analysis_results[2]
            if isinstance(analysis_results[2], str)
            else "风险综述暂时不可用。"
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
        summary = "您尚未录入持仓，录入后可获得个性化风控体检。"
    elif not alerts:
        summary = f"您当前 {len(holdings)} 只持仓整体可控，暂无预警。"
    else:
        summary = f"共 {len(alerts)} 条风险提示，请见下方。"

    # ── 量化风险指标 ──
    metrics_out: PortfolioMetricsOut | None = None
    var_out: VaRResultOut | None = None
    if holdings:
        try:
            holding_quotes = [
                HoldingQuote(
                    symbol=h.symbol,
                    name=h.name,
                    cost_price=h.cost_price,
                    current_price=q.price,
                    quantity=h.quantity,
                    sector=h.sector,
                    buy_date=str(h.buy_date) if h.buy_date else None,
                )
                for h, q in zip(holdings, quotes, strict=True)
            ]
            pm = calculate_portfolio_metrics(holding_quotes)
            metrics_out = PortfolioMetricsOut(
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
            )
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
        except Exception:
            logger.warning("Quantitative metrics calculation failed", exc_info=True)

    return RiskCheckupOut(
        alerts=alerts,
        portfolio_summary=summary,
        llm_analysis=llm_analysis,
        metrics=metrics_out,
        var_result=var_out,
    )
