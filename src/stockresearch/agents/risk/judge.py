"""Risk judge verdict parsing and per-holding action synthesis."""

import json
import re
from dataclasses import dataclass

from stockresearch.core.constants import (
    SEVERITY_CRITICAL,
    SEVERITY_RED,
    SEVERITY_WARNING,
    SEVERITY_YELLOW,
)
from stockresearch.core.schemas import HoldingActionOut, RiskAlertOut
from stockresearch.db.models import Holding

_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")
_VALID_ACTIONS = frozenset({"加仓", "减仓", "持有观望", "暂不调整"})
_VALID_PRIORITIES = frozenset({"高", "中", "低"})


@dataclass(frozen=True)
class JudgeVerdict:
    risk_level: str
    position_action: str
    summary: str
    reason: str
    divergence: str
    analysis_process: str
    holding_actions: tuple[HoldingActionOut, ...]


def derive_portfolio_action(alerts: list[RiskAlertOut]) -> str:
    severities = {a.severity for a in alerts}
    if severities & {SEVERITY_CRITICAL, SEVERITY_RED}:
        return "减仓"
    if not alerts:
        return "加仓"
    if SEVERITY_WARNING in severities or SEVERITY_YELLOW in severities:
        return "持有观望"
    return "持有观望"


def derive_stock_action(
    holding: Holding,
    alerts: list[RiskAlertOut],
) -> HoldingActionOut:
    stock_alerts = [a for a in alerts if a.symbol == holding.symbol]
    severities = {a.severity for a in stock_alerts}
    if severities & {SEVERITY_CRITICAL, SEVERITY_RED}:
        top = stock_alerts[0]
        return HoldingActionOut(
            symbol=holding.symbol,
            name=holding.name,
            action="减仓",
            reason=top.message,
            priority="高",
        )
    if SEVERITY_YELLOW in severities:
        top = next(a for a in stock_alerts if a.severity == SEVERITY_YELLOW)
        return HoldingActionOut(
            symbol=holding.symbol,
            name=holding.name,
            action="持有观望",
            reason=top.message,
            priority="中",
        )
    if SEVERITY_WARNING in severities:
        return HoldingActionOut(
            symbol=holding.symbol,
            name=holding.name,
            action="持有观望",
            reason="组合层面存在集中度等预警，该股暂以观望为主。",
            priority="中",
        )
    return HoldingActionOut(
        symbol=holding.symbol,
        name=holding.name,
        action="暂不调整",
        reason="未触发个股规则告警，当前无需优先处置。",
        priority="低",
    )


def _parse_holding_actions(raw_items: object) -> list[HoldingActionOut]:
    if not isinstance(raw_items, list):
        return []
    parsed: list[HoldingActionOut] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol", "")).strip()
        name = str(item.get("name", "")).strip()
        action = str(item.get("action", "")).strip() or "持有观望"
        reason = str(item.get("reason", "")).strip()
        priority = str(item.get("priority", "中")).strip() or "中"
        if not symbol or not name:
            continue
        if action not in _VALID_ACTIONS:
            action = "持有观望"
        if priority not in _VALID_PRIORITIES:
            priority = "中"
        parsed.append(
            HoldingActionOut(
                symbol=symbol,
                name=name,
                action=action,
                reason=reason or "请结合上文告警与持仓纪律理解。",
                priority=priority,
            )
        )
    return parsed


def ensure_all_holdings_covered(
    holdings: list[Holding],
    actions: list[HoldingActionOut],
    alerts: list[RiskAlertOut],
) -> tuple[HoldingActionOut, ...]:
    by_symbol = {item.symbol: item for item in actions}
    merged: list[HoldingActionOut] = []
    for holding in holdings:
        existing = by_symbol.get(holding.symbol)
        if existing and existing.reason:
            merged.append(existing)
        elif existing:
            fallback = derive_stock_action(holding, alerts)
            merged.append(existing.model_copy(update={"reason": fallback.reason}))
        else:
            merged.append(derive_stock_action(holding, alerts))
    priority_rank = {"高": 0, "中": 1, "低": 2}
    merged.sort(key=lambda item: (priority_rank.get(item.priority, 1), item.symbol))
    return tuple(merged)


def format_judge_display(verdict: JudgeVerdict) -> str:
    lines: list[str] = []
    if verdict.analysis_process:
        lines.append("【分析过程】")
        lines.append(verdict.analysis_process)
    if verdict.holding_actions:
        lines.append(f"【逐股建议】共 {len(verdict.holding_actions)} 只")
        for item in verdict.holding_actions:
            lines.append(
                f"· {item.name}({item.symbol})：{item.action}（优先级{item.priority}）"
                f" — {item.reason}"
            )
    lines.append("【组合结论】")
    lines.append(verdict.summary)
    if verdict.reason and verdict.reason != verdict.summary:
        lines.append(verdict.reason)
    lines.append(f"整体风险{verdict.risk_level}，组合倾向{verdict.position_action}，分歧{verdict.divergence}。")
    return "\n".join(lines)


def parse_judge(
    raw: str,
    alerts: list[RiskAlertOut],
    holdings: list[Holding],
) -> JudgeVerdict:
    fallback_action = derive_portfolio_action(alerts)
    fallback_actions = tuple(derive_stock_action(h, alerts) for h in holdings)
    fallback_process = (
        "1. 扫描规则引擎告警，识别回撤、黑天鹅与集中度风险。\n"
        "2. 结合市场、相关性与情景分析，评估组合联动暴露。\n"
        "3. 对照三方辩论与 Research Manager 意见，形成逐股与组合结论。"
    )
    match = _JSON_BLOCK.search(raw)
    if match:
        try:
            data = json.loads(match.group(0))
            risk_level = str(data.get("risk_level", "中")).strip() or "中"
            action = str(data.get("position_action", fallback_action)).strip() or fallback_action
            summary = str(data.get("summary", "")).strip()
            reason = str(data.get("reason", "")).strip()
            divergence = str(data.get("divergence", "分歧中等")).strip()
            analysis_process = str(data.get("analysis_process", "")).strip()
            holding_actions = ensure_all_holdings_covered(
                holdings,
                _parse_holding_actions(data.get("holding_actions")),
                alerts,
            )
            if action not in ("加仓", "减仓", "持有观望"):
                action = fallback_action
            if risk_level not in ("低", "中", "高"):
                risk_level = "中"
            return JudgeVerdict(
                risk_level=risk_level,
                position_action=action,
                summary=summary or "请您结合告警与持仓纪律自行判断。",
                reason=reason or summary or "告警与持仓结构共同指向当前判断。",
                divergence=divergence or "分歧中等",
                analysis_process=analysis_process or fallback_process,
                holding_actions=holding_actions or fallback_actions,
            )
        except json.JSONDecodeError:
            pass
    plain = raw.strip()
    has_severe = any(a.severity in (SEVERITY_CRITICAL, SEVERITY_RED) for a in alerts)
    risk_level = "高" if has_severe else "中"
    if not alerts:
        risk_level = "低"
    return JudgeVerdict(
        risk_level=risk_level,
        position_action=fallback_action,
        summary=plain or "风控会诊完成。",
        reason=plain or "请结合告警与持仓结构理解当前风险。",
        divergence="分歧中等",
        analysis_process=fallback_process,
        holding_actions=fallback_actions,
    )


def portfolio_summary_text(verdict: JudgeVerdict) -> str:
    action_bits = "；".join(
        f"{item.name}{item.action}" for item in verdict.holding_actions
    )
    suffix = f"逐股：{action_bits}" if action_bits else verdict.summary
    return (
        f"{verdict.risk_level}风险 · 组合倾向{verdict.position_action} · "
        f"{verdict.summary} {suffix}"
    ).strip()
