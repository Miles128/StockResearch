"""Deterministic ThesisOut builder (Phase 10 W3)."""

from __future__ import annotations

import re


from stockresearch.core.schemas import (
    DeepAnalysisOut,
    DimensionResult,
    ImpactOut,
    NumericFactorOut,
    PricingBridgeOut,
    ResearchReportOut,
    ThesisOut,
)
from stockresearch.services.thesis_build import build_thesis

_FORBIDDEN = re.compile(
    r"买入|卖出|建仓|清仓|加仓|减仓|\bBUY\b|\bSELL\b",
    re.IGNORECASE,
)


def _assert_no_trade_verbs(text: str) -> None:
    assert not _FORBIDDEN.search(text), f"forbidden trade verb in: {text!r}"


def _assert_thesis_compliant(thesis: ThesisOut) -> None:
    _assert_no_trade_verbs(thesis.claim)
    for item in thesis.monitors:
        _assert_no_trade_verbs(item)
    for item in thesis.invalidate_if:
        _assert_no_trade_verbs(item)
    if thesis.scenarios:
        for item in thesis.scenarios.values():
            _assert_no_trade_verbs(item)


def _bullish_report(*, with_impact: bool = True) -> ResearchReportOut:
    impact = None
    if with_impact:
        impact = ImpactOut(
            window_trading_days=20,
            stock_return_pct=8.0,
            market_contrib_pct=3.0,
            industry_contrib_pct=1.0,
            idio_return_pct=4.0,
            partial=False,
            gaps=[],
        )
    return ResearchReportOut(
        symbol="600519",
        name="贵州茅台",
        dimensions={
            "fundamental": DimensionResult(
                agent="基本面",
                score=8.0,
                confidence="high",
                analysis="盈利稳健",
                highlights=["营收与净利双位数增长"],
                risks=["估值偏高"],
                data_sources=["mock"],
            ),
            "technical": DimensionResult(
                agent="技术面",
                score=6.5,
                confidence="medium",
                analysis="动量偏强",
                highlights=["20日动量为正"],
                risks=["短线超买"],
                data_sources=["mock"],
            ),
        },
        composite_score=7.5,
        composite_confidence="high",
        bias="bullish",
        summary="贵州茅台偏多。",
        factors=[
            NumericFactorOut(
                key="momentum_20d",
                label="20日动量",
                value=5.2,
                as_of="2026-07-20",
                unit="%",
            ),
            NumericFactorOut(
                key="np_yoy",
                label="净利同比",
                value=12.0,
                as_of="2026-03-31",
                unit="%",
            ),
        ],
        analysis_depth="deep",
        deep_analysis=DeepAnalysisOut(impact=impact, pricing=None, thesis=None),
    )


def test_build_thesis_claim_uses_bias_highlight_and_idio() -> None:
    thesis = build_thesis(_bullish_report())
    assert "偏多" in thesis.claim
    assert "营收与净利双位数增长" in thesis.claim
    assert "特质收益为正" in thesis.claim
    _assert_thesis_compliant(thesis)


def test_build_thesis_evidence_ids() -> None:
    thesis = build_thesis(_bullish_report())
    assert "dim:fundamental" in thesis.evidence_ids
    assert "dim:technical" in thesis.evidence_ids
    assert "factor:momentum_20d" in thesis.evidence_ids
    assert "factor:np_yoy" in thesis.evidence_ids
    assert "impact:idio" in thesis.evidence_ids
    assert "impact:market" in thesis.evidence_ids
    assert "impact:industry" in thesis.evidence_ids


def test_build_thesis_horizon_from_impact_window() -> None:
    thesis = build_thesis(_bullish_report())
    assert thesis.horizon == "20个交易日观察窗"


def test_build_thesis_horizon_custom_window() -> None:
    report = _bullish_report()
    assert report.deep_analysis is not None
    assert report.deep_analysis.impact is not None
    report.deep_analysis.impact.window_trading_days = 60
    thesis = build_thesis(report)
    assert thesis.horizon == "60个交易日观察窗"


def test_build_thesis_monitors_from_gaps_and_factors() -> None:
    report = _bullish_report()
    assert report.deep_analysis is not None
    assert report.deep_analysis.impact is not None
    report.deep_analysis.impact.partial = True
    report.deep_analysis.impact.gaps = ["行业代理样本不足"]
    report.dimensions["fundamental"].gaps = ["缺少最新季报"]
    thesis = build_thesis(report)
    assert "行业代理样本不足" in thesis.monitors
    assert "缺少最新季报" in thesis.monitors
    assert any("momentum_20d" in m or "20日动量" in m for m in thesis.monitors)
    _assert_thesis_compliant(thesis)


def test_build_thesis_invalidate_if_opposes_bullish_claim() -> None:
    thesis = build_thesis(_bullish_report())
    assert len(thesis.invalidate_if) >= 2
    joined = " ".join(thesis.invalidate_if)
    assert "动量" in joined or "momentum" in joined.lower()
    assert "特质" in joined
    _assert_thesis_compliant(thesis)


def test_build_thesis_bearish_negative_idio() -> None:
    report = _bullish_report()
    report.bias = "bearish"
    assert report.deep_analysis is not None
    assert report.deep_analysis.impact is not None
    report.deep_analysis.impact.idio_return_pct = -3.5
    report.dimensions["fundamental"].highlights = ["盈利增速放缓"]
    report.dimensions["fundamental"].score = 4.0
    thesis = build_thesis(report)
    assert "偏空" in thesis.claim
    assert "特质收益为负" in thesis.claim
    assert any("转强" in c or "偏多" in c for c in thesis.invalidate_if)
    _assert_thesis_compliant(thesis)


def test_build_thesis_partial_without_impact() -> None:
    report = _bullish_report(with_impact=False)
    thesis = build_thesis(report)
    assert thesis.partial is True
    assert "特质收益待验证" in thesis.claim
    assert "impact:idio" not in thesis.evidence_ids
    _assert_thesis_compliant(thesis)


def test_build_thesis_includes_pricing_evidence() -> None:
    report = _bullish_report()
    assert report.deep_analysis is not None
    report.deep_analysis.pricing = PricingBridgeOut(
        window_label="60d qfq",
        price_change_pct=10.0,
        earnings_contrib_pct=6.0,
        multiple_contrib_pct=4.0,
        factor_keys_used=["np_yoy", "pe_ttm"],
        partial=False,
    )
    thesis = build_thesis(report)
    assert "pricing:bridge" in thesis.evidence_ids
    _assert_thesis_compliant(thesis)


def test_build_thesis_is_deterministic() -> None:
    report = _bullish_report()
    assert build_thesis(report).model_dump() == build_thesis(report).model_dump()

