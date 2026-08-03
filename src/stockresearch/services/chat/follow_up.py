"""Rule-based follow-up question suggestions — no LLM."""

from __future__ import annotations

import logging

from stockresearch.agents.output_style import get_reading_mode
from stockresearch.core.constants import INTENT_RISK
from stockresearch.core.schemas import AshareFactorOut, ResearchReportOut

logger = logging.getLogger(__name__)


def _research_from_cards(cards: list[dict[str, object]]) -> ResearchReportOut | None:
    for card in cards:
        if card.get("type") != "research":
            continue
        data = card.get("data")
        if isinstance(data, dict):
            try:
                return ResearchReportOut.model_validate(data)
            except Exception:
                logger.debug("research card validation failed for follow-up", exc_info=True)
                return None
    return None


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out[:4]


def build_follow_up_questions(
    *,
    intent: str,
    cards: list[dict[str, object]],
    reading_mode: str | None = None,
) -> list[str]:
    """Return 2–4 contextual follow-up prompts based on intent and cards."""
    mode = reading_mode or get_reading_mode()
    professional = mode == "professional"
    report = _research_from_cards(cards)
    symbol = report.symbol if report else None
    name = report.name if report else None
    questions: list[str] = []

    if intent == INTENT_RISK or any(c.get("type") == "risk" for c in cards):
        questions.append(
            "谁对组合风险贡献最大？请按持仓拆解。"
            if not professional
            else "请按风险贡献排序持仓，并展开 VaR 与集中度依据。"
        )
        questions.append(
            "如果市场再跌 10%，我的组合大概会亏多少？"
            if not professional
            else "在压力情景下，组合最大回撤与金额化损失是多少？"
        )

    if report:
        missing = [gap for factor in report.ashare_factors for gap in factor.missing]
        if missing:
            questions.append(
                "哪些数据补齐后，这个结论可能会变化？"
                if not professional
                else "列出当前缺失因子及对应数据源，哪些补齐后可能改变结论？"
            )
        if symbol and name:
            questions.append(
                f"用专业模式展开{name}的估值和盈利质量。"
                if not professional
                else f"展开{name}({symbol})的估值分位、盈利质量与财务缺口。"
            )
        questions.append(
            "哪些依据最可能推翻这个结论？"
            if not professional
            else "哪些数据或事件最可能推翻当前多空倾向？"
        )

    if any(c.get("type") == "news" for c in cards):
        questions.append(
            "这条新闻对我的其他持仓有影响吗？"
            if not professional
            else "这条新闻对组合内其他标的的传导路径是什么？"
        )

    if not questions:
        questions.append(
            "今天与我持仓最相关的变化是什么？"
            if not professional
            else "基于当前持仓，今天最值得验证的三条数据是什么？"
        )
        questions.append(
            "哪些依据最可能推翻这个结论？"
            if not professional
            else "当前回答中置信度最低的部分是哪些？"
        )

    return _dedupe(questions)


def attach_report_follow_ups(report: ResearchReportOut) -> ResearchReportOut:
    """Attach rule-based follow-ups to a persisted research report."""
    gaps = list(report.data_gaps)
    if not gaps:
        gaps = _data_gaps_from_factors(report.ashare_factors)
    cards = [{"type": "research", "data": report.model_dump(mode="json")}]
    follow_ups = build_follow_up_questions(intent="research", cards=cards)
    return report.model_copy(update={"data_gaps": gaps[:5], "follow_up_questions": follow_ups})


def _data_gaps_from_factors(factors: list[AshareFactorOut]) -> list[str]:
    gaps: list[str] = []
    for factor in factors:
        for item in factor.missing:
            if item not in gaps:
                gaps.append(item)
            if len(gaps) >= 5:
                return gaps
    return gaps
