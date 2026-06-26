"""Shared research report assembly — weighted score + text factors."""

from typing import Literal

from stockresearch.agents.research.scoring import (
    composite_confidence as resolve_composite_confidence,
)
from stockresearch.agents.research.scoring import (
    score_bias,
    weighted_composite_score,
)
from stockresearch.core.schemas import (
    DebateResult,
    DimensionResult,
    ResearchReportOut,
    SectorLeaderBrief,
)
from stockresearch.services.ashare_factors import build_ashare_factor_checklist
from stockresearch.services.text_factor import build_text_factor_summary


def build_research_report(
    symbol: str,
    name: str,
    dimensions: dict[str, DimensionResult],
    debate: DebateResult | None,
    *,
    dimension_labels: dict[str, str],
    news_text_factor: str | None = None,
    sector: str | None = None,
    leaders: list[SectorLeaderBrief] | None = None,
    summary_prefix: str | None = None,
) -> ResearchReportOut:
    composite, weights = weighted_composite_score(dimensions)
    composite_confidence = resolve_composite_confidence(dimensions)
    bias = score_bias(composite)

    bias_label = "偏多" if bias == "bullish" else "偏空" if bias == "bearish" else "中性"
    score_tail = f"加权综合 {composite}/10，倾向{bias_label}。"
    if summary_prefix:
        summary = f"{summary_prefix.rstrip('。')}。{score_tail}"
    else:
        summary = f"{name}({symbol}) {score_tail}"
    if debate:
        judge_label: Literal["偏多", "偏空", "中性"] = (
            "偏多" if debate.final_bias == "bullish"
            else "偏空" if debate.final_bias == "bearish"
            else "中性"
        )
        summary += f" 裁判{judge_label}：{debate.consensus}"

    text_factor_summary = build_text_factor_summary(
        subject=name if not sector else f"「{sector}」板块",
        dimensions=dimensions,
        dimension_labels=dimension_labels,
        composite_score=composite,
        composite_confidence=composite_confidence,
        dimension_weights=weights,
        news_text_factor=news_text_factor,
        debate_consensus=debate.consensus if debate else None,
    )

    return ResearchReportOut(
        symbol=symbol,
        name=name,
        sector=sector,
        dimensions=dimensions,
        composite_score=composite,
        composite_confidence=composite_confidence,
        bias=bias,
        summary=summary,
        debate=debate,
        leaders=leaders or [],
        news_text_factor=news_text_factor,
        text_factor_summary=text_factor_summary,
        ashare_factors=build_ashare_factor_checklist(
            dimensions,
            news_text_factor=news_text_factor,
        ),
        dimension_weights=weights,
    )
