"""Shared research report assembly — weighted score + text factors."""

from typing import Literal

from stockresearch.agents.research.dimension_text import build_brief_summary
from stockresearch.agents.research.scoring import (
    composite_confidence as resolve_composite_confidence,
)
from stockresearch.agents.research.scoring import (
    score_bias,
    weighted_composite_score,
)
from stockresearch.agents.research.summary_length import normalize_summary
from stockresearch.core.schemas import (
    DimensionResult,
    ResearchReportOut,
    SectorLeaderBrief,
)
from stockresearch.services.ashare_factors import build_ashare_factor_checklist
from stockresearch.services.text_factor import build_text_factor_summary

_DIM_ORDER = (
    "fundamental",
    "technical",
    "sentiment",
    "chips",
    "macro",
    "industry",
    "policy",
    "capital",
    "valuation",
    "structure",
)


def _dimension_expand_parts(dimensions: dict[str, DimensionResult]) -> list[str]:
    parts: list[str] = []
    for key in _DIM_ORDER:
        dim = dimensions.get(key)
        if dim is None:
            continue
        for highlight in dim.highlights[:2]:
            line = highlight.strip()
            if line and line not in parts:
                parts.append(line)
        if len(parts) >= 6:
            break
    return parts


def _collect_report_gaps(dimensions: dict[str, DimensionResult], ashare_factors: list) -> list[str]:
    data_gaps: list[str] = []
    for dim in dimensions.values():
        for gap in dim.gaps:
            if gap not in data_gaps:
                data_gaps.append(gap)
            if len(data_gaps) >= 5:
                return data_gaps
    for factor in ashare_factors:
        for gap in factor.missing:
            if gap not in data_gaps:
                data_gaps.append(gap)
            if len(data_gaps) >= 5:
                return data_gaps
    return data_gaps


def build_research_report(
    symbol: str,
    name: str,
    dimensions: dict[str, DimensionResult],
    *,
    dimension_labels: dict[str, str],
    news_text_factor: str | None = None,
    sector: str | None = None,
    leaders: list[SectorLeaderBrief] | None = None,
    summary_prefix: str | None = None,
    factors: list | None = None,
    bars_provenance: object | None = None,
    analysis_depth: Literal["standard", "comprehensive", "deep"] = "standard",
    factors_expanded: bool = False,
    factor_alignment_note: str | None = None,
    enable_signal_verify_hook: bool = False,
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
    expand_parts = _dimension_expand_parts(dimensions)
    summary = normalize_summary(summary, expand_parts=expand_parts, min_len=200, max_len=320)

    text_factor_summary = build_text_factor_summary(
        subject=name if not sector else f"「{sector}」板块",
        dimensions=dimensions,
        dimension_labels=dimension_labels,
        composite_score=composite,
        composite_confidence=composite_confidence,
        dimension_weights=weights,
        news_text_factor=news_text_factor,
    )

    ashare_factors = build_ashare_factor_checklist(
        dimensions,
        news_text_factor=news_text_factor,
    )
    from stockresearch.agents.research.viewpoints import build_viewpoints

    viewpoints = build_viewpoints(dimensions, news_text_factor=news_text_factor)
    data_gaps = _collect_report_gaps(dimensions, ashare_factors)
    if bars_provenance is not None and getattr(bars_provenance, "partial", False):
        note = getattr(bars_provenance, "note", None) or "日线前复权不完整"
        if note not in data_gaps and len(data_gaps) < 5:
            data_gaps.append(note)
    brief_summary = build_brief_summary(
        name=name,
        symbol=symbol,
        bias=bias,
        composite_score=composite,
        dimensions=dimensions,
        dimension_labels=dimension_labels,
    )

    report = ResearchReportOut(
        symbol=symbol,
        name=name,
        sector=sector,
        dimensions=dimensions,
        composite_score=composite,
        composite_confidence=composite_confidence,
        bias=bias,
        summary=summary,
        brief_summary=brief_summary,
        viewpoints=viewpoints,
        data_gaps=data_gaps,
        leaders=leaders or [],
        news_text_factor=news_text_factor,
        text_factor_summary=text_factor_summary,
        ashare_factors=ashare_factors,
        factors=list(factors or []),
        bars_provenance=bars_provenance,  # type: ignore[arg-type]
        dimension_weights=weights,
        analysis_depth=analysis_depth,
        factors_expanded=factors_expanded,
        factor_alignment_note=factor_alignment_note,
        enable_signal_verify_hook=enable_signal_verify_hook,
    )
    from stockresearch.services.chat.follow_up import attach_report_follow_ups

    return attach_report_follow_ups(report)
