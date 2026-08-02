"""Deterministic ThesisOut builder for deep analysis (Phase 10 W3).

No LLM — Chinese templates from bias, dimension highlights, impact idio sign,
partial gaps, and thesis-relevant numeric factors.
"""

from __future__ import annotations

from stockresearch.core.schemas import ImpactOut, ResearchReportOut, ThesisOut

_BIAS_LABEL = {"bullish": "偏多", "bearish": "偏空", "neutral": "中性"}

# Numeric factor keys worth tracking in monitors / invalidation.
_THESIS_FACTOR_KEYS = (
    "momentum_20d",
    "momentum_60d",
    "np_yoy",
    "revenue_yoy",
    "pe_ttm",
    "roe",
    "vol_ann",
)


def _top_highlight(report: ResearchReportOut) -> str:
    if not report.dimensions:
        return "四维证据待补充"
    best_key = max(report.dimensions, key=lambda k: report.dimensions[k].score)
    dim = report.dimensions[best_key]
    if dim.highlights:
        return dim.highlights[0]
    if dim.analysis:
        return dim.analysis[:48].rstrip()
    return "暂无要点"


def _idio_phrase(impact: ImpactOut | None) -> str:
    if impact is None or impact.idio_return_pct is None:
        return "特质收益待验证"
    pct = impact.idio_return_pct
    if pct > 0:
        return f"特质收益为正（{pct:+.1f}%）"
    if pct < 0:
        return f"特质收益为负（{pct:+.1f}%）"
    return "特质收益接近零"


def _build_claim(report: ResearchReportOut) -> str:
    bias = _BIAS_LABEL.get(report.bias, report.bias)
    highlight = _top_highlight(report)
    impact = report.deep_analysis.impact if report.deep_analysis else None
    idio = _idio_phrase(impact)
    return f"综合倾向{bias}，{highlight}，近期{idio}。"


def _evidence_ids(report: ResearchReportOut) -> list[str]:
    ids: list[str] = []
    for key in sorted(report.dimensions, key=lambda k: (-report.dimensions[k].score, k)):
        ids.append(f"dim:{key}")
    for factor in report.factors:
        ids.append(f"factor:{factor.key}")
    if report.deep_analysis is not None:
        impact = report.deep_analysis.impact
        if impact is not None:
            ids.append("impact:idio")
            if impact.market_contrib_pct is not None:
                ids.append("impact:market")
            if impact.industry_contrib_pct is not None:
                ids.append("impact:industry")
        if report.deep_analysis.pricing is not None:
            ids.append("pricing:bridge")
    return ids


def _collect_gaps(report: ResearchReportOut) -> list[str]:
    gaps: list[str] = []
    for dim in report.dimensions.values():
        for gap in dim.gaps:
            if gap and gap not in gaps:
                gaps.append(gap)
    for gap in report.data_gaps:
        if gap and gap not in gaps:
            gaps.append(gap)
    if report.deep_analysis is not None:
        if report.deep_analysis.impact is not None:
            for gap in report.deep_analysis.impact.gaps:
                if gap and gap not in gaps:
                    gaps.append(gap)
        if report.deep_analysis.pricing is not None:
            for gap in report.deep_analysis.pricing.gaps:
                if gap and gap not in gaps:
                    gaps.append(gap)
    return gaps


def _monitors(report: ResearchReportOut) -> list[str]:
    monitors = list(_collect_gaps(report))
    for factor in report.factors:
        if factor.key not in _THESIS_FACTOR_KEYS:
            continue
        label = factor.label or factor.key
        entry = f"补全因子：{label}" if factor.partial else f"跟踪因子：{label}"
        if entry not in monitors:
            monitors.append(entry)
    return monitors


def _invalidate_if(report: ResearchReportOut) -> list[str]:
    conditions: list[str] = []
    if report.bias == "bullish":
        conditions.append("综合评分转弱且倾向转为偏空或中性")
    elif report.bias == "bearish":
        conditions.append("综合评分转强且倾向转为偏多或中性")
    else:
        conditions.append("四维评分出现明显单边分化")

    impact = report.deep_analysis.impact if report.deep_analysis else None
    if impact is not None and impact.idio_return_pct is not None:
        if impact.idio_return_pct > 0:
            conditions.append("特质收益峰日无法解释且后续转负")
        elif impact.idio_return_pct < 0:
            conditions.append("特质拖累扩大且缺乏事件解释")
        else:
            conditions.append("特质收益方向与当前判断背离")
        if impact.peak_days and any(p.unexplained for p in impact.peak_days):
            conditions.append("未解释特质峰日增多")

    momentum = next((f for f in report.factors if f.key == "momentum_20d"), None)
    if momentum is not None and momentum.value is not None:
        if momentum.value > 0:
            conditions.append("20日动量转负")
        elif momentum.value < 0:
            conditions.append("20日动量转正")
        else:
            conditions.append("20日动量方向反转")

    return conditions


def _horizon(report: ResearchReportOut) -> str:
    impact = report.deep_analysis.impact if report.deep_analysis else None
    if impact is not None and impact.window_trading_days:
        return f"{impact.window_trading_days}个交易日观察窗"
    return "20个交易日观察窗"


def _is_partial(report: ResearchReportOut) -> bool:
    if report.deep_analysis is None or report.deep_analysis.impact is None:
        return True
    if report.deep_analysis.impact.partial:
        return True
    if _collect_gaps(report):
        return True
    if not report.dimensions:
        return True
    return False


def build_thesis(report: ResearchReportOut) -> ThesisOut:
    """Build a deterministic research thesis from a report snapshot."""
    return ThesisOut(
        claim=_build_claim(report),
        evidence_ids=_evidence_ids(report),
        monitors=_monitors(report),
        invalidate_if=_invalidate_if(report),
        horizon=_horizon(report),
        partial=_is_partial(report),
    )
