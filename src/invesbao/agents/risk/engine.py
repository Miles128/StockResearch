"""Risk engine — rule-based thresholds + LLM-driven analysis."""

import asyncio
import logging

from invesbao.core.constants import (
    SEVERITY_CRITICAL,
    SEVERITY_RED,
    SEVERITY_WARNING,
    SEVERITY_YELLOW,
)
from invesbao.core.schemas import LLMRiskAnalysis, RiskAlertOut, RiskCheckupOut
from invesbao.data.providers.market import QuoteProvider
from invesbao.db.models import Holding
from invesbao.agents.voice import AGENT_VOICE
from invesbao.utils.llm import LLMClient, get_llm_client

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

        humanize_results = await asyncio.gather(*humanize_tasks)
        for alert, human_msg in zip(alerts, humanize_results):
            alert.human_message = human_msg

        market_assessment, correlation_analysis, risk_narrative, scenario_analysis = (
            await asyncio.gather(*analysis_tasks)
        )
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

    return RiskCheckupOut(alerts=alerts, portfolio_summary=summary, llm_analysis=llm_analysis)
