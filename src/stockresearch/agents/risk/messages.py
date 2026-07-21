"""Locale-aware risk checkup copy (rule alerts, summaries, fallbacks)."""

from __future__ import annotations

from stockresearch.agents.output_style import get_output_locale


def _en() -> bool:
    return get_output_locale() == "en"


def alert_stop_loss_red(
    name: str, symbol: str, cost: float, price: float, drawdown: float
) -> str:
    if _en():
        return (
            f"{name} ({symbol}) drawdown from cost {cost:.2f} to {price:.2f}, "
            f"loss {drawdown:.0%} — red stop-loss alert triggered."
        )
    return (
        f"{name}({symbol}) 从成本 {cost:.2f} 回撤至 {price:.2f}，"
        f"亏损 {drawdown:.0%}，触发红色止损预警。"
    )


def alert_stop_loss_yellow(name: str, symbol: str, drawdown: float) -> str:
    if _en():
        return (
            f"{name} ({symbol}) drawdown {drawdown:.0%}, "
            f"approaching your 8% watch zone."
        )
    return (
        f"{name}({symbol}) 回撤 {drawdown:.0%}，"
        f"接近你设定的止损关注区间（8%）。"
    )


def alert_stop_loss_yellow_short(name: str, symbol: str, drawdown: float) -> str:
    if _en():
        return f"{name} ({symbol}) drawdown {drawdown:.0%}."
    return f"{name}({symbol}) 回撤 {drawdown:.0%}。"


def alert_black_swan_drop(name: str, change_pct: float) -> str:
    if _en():
        return (
            f"{name} fell sharply today ({change_pct:.1f}%) — "
            f"check for major negative news."
        )
    return f"{name} 今日大跌 {change_pct}%，请关注是否有重大利空。"


def alert_black_swan_tag(name: str, tag: str) -> str:
    if _en():
        return f"{name} carries a {tag}-related risk flag — review announcements."
    return f"{name} 存在 {tag} 相关风险标签，请重点关注公告。"


def alert_black_swan_tag_short(name: str, tag: str) -> str:
    if _en():
        return f"{name} has a {tag}-related risk flag."
    return f"{name} 存在 {tag} 相关风险标签。"


def alert_concentration(sector: str, ratio: float) -> str:
    if _en():
        return (
            f"Sector concentration is elevated: {sector} is {ratio:.0%} of the book "
            f"(above the 40% threshold)."
        )
    return f"行业集中度偏高：{sector} 占仓位 {ratio:.0%}，超过 40% 阈值。"


def alert_concentration_short(sector: str, ratio: float) -> str:
    if _en():
        return f"Sector concentration elevated: {sector} at {ratio:.0%}."
    return f"行业集中度偏高：{sector} 占仓位 {ratio:.0%}。"


def alert_single_name_concentration(name: str, symbol: str, ratio: float) -> str:
    if _en():
        return (
            f"Single-name concentration is elevated: {name} ({symbol}) is {ratio:.0%} "
            f"of the book (above the 30% threshold)."
        )
    return f"个股集中度偏高：{name}({symbol}) 占仓位 {ratio:.0%}，超过 30% 阈值。"


def portfolio_summary_no_holdings() -> str:
    if _en():
        return "No holdings on file — add positions for a personalized risk checkup."
    return "您尚未录入持仓，录入后可获得个性化风控体检。"


def portfolio_summary_all_clear(count: int) -> str:
    if _en():
        return f"Your {count} holding(s) look manageable — no rule alerts for now."
    return f"您当前 {count} 只持仓整体可控，暂无预警。"


def portfolio_summary_with_alerts(count: int) -> str:
    if _en():
        return f"{count} risk alert(s) — see details below."
    return f"共 {count} 条风险提示，请见下方。"


def llm_unavailable_market() -> str:
    return "Market assessment is temporarily unavailable." if _en() else "市场环境评估暂时不可用。"


def llm_unavailable_correlation() -> str:
    return "Correlation analysis is temporarily unavailable." if _en() else "相关性分析暂时不可用。"


def llm_unavailable_narrative() -> str:
    return "Risk narrative is temporarily unavailable." if _en() else "风险综述暂时不可用。"


def llm_no_holdings_market() -> str:
    return "No holdings — cannot assess market impact." if _en() else "无持仓，无法评估市场环境。"


def llm_insufficient_correlation() -> str:
    return "Fewer than two holdings — correlation review not needed." if _en() else "持仓不足两只，无需分析相关性。"


def llm_no_narrative_needed() -> str:
    return "No holdings — risk narrative not required." if _en() else "暂无持仓，无需生成风险叙述。"


def rules_scan_summary(holdings_count: int, alerts_count: int) -> str:
    if _en():
        if holdings_count == 0:
            return "No holdings."
        return f"Scanned {holdings_count} holding(s), {alerts_count} alert(s) triggered."
    if holdings_count == 0:
        return "暂无持仓。"
    return f"扫描 {holdings_count} 只，触发 {alerts_count} 条告警。"


def localize_risk_level(level: str) -> str:
    mapping = {"低": "Low", "中": "Medium", "高": "High"}
    if _en():
        return mapping.get(level, level)
    return level


def localize_position_action(action: str) -> str:
    from stockresearch.services.compliance_language import normalize_position_action

    normalized = normalize_position_action(action, portfolio=False)
    mapping = {
        "仓位偏高": "Overweight",
        "仓位偏低": "Underweight",
        "仓位适中": "Balanced",
        "建议控制仓位": "Consider position sizing",
        "暂不调整": "No change for now",
    }
    if _en():
        return mapping.get(normalized, normalized)
    return normalized


def portfolio_summary_verdict(
    risk_level: str,
    position_action: str,
    summary: str,
    holding_bits: str,
) -> str:
    if _en():
        rl = localize_risk_level(risk_level)
        pa = localize_position_action(position_action)
        suffix = f"Per holding: {holding_bits}" if holding_bits else summary
        return f"{rl} risk · Portfolio bias {pa} · {summary} {suffix}".strip()
    suffix = f"逐股：{holding_bits}" if holding_bits else summary
    return f"{risk_level}风险 · 组合仓位倾向{position_action} · {summary} {suffix}".strip()
