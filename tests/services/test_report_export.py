"""Export helpers for machine-readable research reports."""

from stockresearch.core.schemas import (
    BarsProvenanceOut,
    DimensionResult,
    NumericFactorOut,
    ResearchReportOut,
)
from stockresearch.services.report_export import (
    report_machine_payload,
    report_to_csv,
    report_to_json,
    report_to_markdown,
)


def _mini_report() -> ResearchReportOut:
    return ResearchReportOut(
        symbol="600519",
        name="贵州茅台",
        dimensions={
            "fundamental": DimensionResult(
                agent="基本面",
                score=7.0,
                confidence="medium",
                analysis="ok",
                highlights=["营收稳定"],
                risks=["估值偏高"],
                data_sources=["mock"],
            )
        },
        composite_score=7.0,
        composite_confidence="medium",
        bias="bullish",
        summary="贵州茅台(600519) 加权综合 7.0/10，倾向偏多。" * 2,
        analysis_depth="comprehensive",
        factors=[
            NumericFactorOut(
                key="momentum_20d",
                label="20日动量",
                value=3.5,
                as_of="2026-07-20",
                unit="%",
                bars_adjust="qfq",
                bars_source="mock",
            )
        ],
        bars_provenance=BarsProvenanceOut(
            source="mock",
            adjust="qfq",
            as_of="2026-07-20",
            partial=False,
        ),
        factor_alignment_note="因子与结论大致同向：动量为正",
    )


def test_report_to_json_includes_provenance_and_factors() -> None:
    payload = report_machine_payload(_mini_report())
    assert payload["schema"] == "stockresearch.report.v1"
    assert payload["symbol"] == "600519"
    assert payload["bars_provenance"]["adjust"] == "qfq"
    assert payload["factors"][0]["key"] == "momentum_20d"
    text = report_to_json(_mini_report())
    assert '"momentum_20d"' in text


def test_report_to_csv_has_factor_row() -> None:
    csv_text = report_to_csv(_mini_report())
    assert "momentum_20d" in csv_text
    assert "600519" in csv_text
    assert "qfq" in csv_text


def test_markdown_includes_numeric_factors_section() -> None:
    md = report_to_markdown(_mini_report())
    assert "## 数值因子" in md
    assert "## 日线口径" in md
    assert "comprehensive" in md


def test_export_includes_deep_analysis_impact() -> None:
    from stockresearch.core.schemas import DeepAnalysisOut, ImpactOut

    r = _mini_report()
    r.analysis_depth = "deep"
    r.deep_analysis = DeepAnalysisOut(
        impact=ImpactOut(
            window_trading_days=20,
            stock_return_pct=1.0,
            market_contrib_pct=0.5,
            industry_contrib_pct=0.2,
            idio_return_pct=0.3,
            partial=False,
        )
    )
    payload = report_machine_payload(r)
    assert payload["deep_analysis"]["impact"]["window_trading_days"] == 20
    assert payload["deep_analysis"]["impact"]["stock_return_pct"] == 1.0


def test_markdown_includes_deep_analysis_impact_section() -> None:
    from stockresearch.core.schemas import DeepAnalysisOut, ImpactOut

    r = _mini_report()
    r.analysis_depth = "deep"
    r.deep_analysis = DeepAnalysisOut(
        impact=ImpactOut(
            window_trading_days=20,
            stock_return_pct=2.5,
            market_contrib_pct=1.0,
            industry_contrib_pct=0.4,
            idio_return_pct=1.1,
            partial=False,
        )
    )
    md = report_to_markdown(r)
    assert "## 深度分析 · 影响" in md
    assert "2.5" in md
    assert "1.0" in md
    assert "0.4" in md
    assert "1.1" in md


def test_markdown_omits_deep_analysis_when_absent() -> None:
    md = report_to_markdown(_mini_report())
    assert "## 深度分析 · 影响" not in md


def test_machine_payload_deep_analysis_none_when_absent() -> None:
    payload = report_machine_payload(_mini_report())
    assert payload["deep_analysis"] is None


def test_export_includes_deep_analysis_pricing() -> None:
    from stockresearch.core.schemas import DeepAnalysisOut, PricingBridgeOut

    r = _mini_report()
    r.analysis_depth = "deep"
    r.deep_analysis = DeepAnalysisOut(
        pricing=PricingBridgeOut(
            window_label="60d qfq",
            price_change_pct=8.5,
            earnings_contrib_pct=4.2,
            multiple_contrib_pct=None,
            pe_start=None,
            pe_end=28.0,
            implied_growth_pct=None,
            factor_keys_used=["np_yoy", "pe_percentile"],
            partial=True,
            gaps=["pe_start 不可用"],
        )
    )
    payload = report_machine_payload(r)
    assert payload["deep_analysis"]["pricing"]["price_change_pct"] == 8.5
    assert payload["deep_analysis"]["pricing"]["pe_end"] == 28.0


def test_markdown_includes_deep_analysis_pricing_section() -> None:
    from stockresearch.core.schemas import DeepAnalysisOut, PricingBridgeOut

    r = _mini_report()
    r.analysis_depth = "deep"
    r.deep_analysis = DeepAnalysisOut(
        pricing=PricingBridgeOut(
            window_label="60d qfq",
            price_change_pct=6.5,
            earnings_contrib_pct=3.0,
            multiple_contrib_pct=None,
            pe_start=None,
            pe_end=22.0,
            implied_growth_pct=None,
            factor_keys_used=["np_yoy"],
            partial=True,
            gaps=["pe_start 不可用"],
        )
    )
    md = report_to_markdown(r)
    assert "## 深度分析 · 定价桥" in md
    assert "6.5" in md
    assert "3.0" in md
    assert "22.0" in md
    assert "np_yoy" in md


def test_markdown_includes_both_impact_and_pricing_sections() -> None:
    from stockresearch.core.schemas import DeepAnalysisOut, ImpactOut, PricingBridgeOut

    r = _mini_report()
    r.analysis_depth = "deep"
    r.deep_analysis = DeepAnalysisOut(
        impact=ImpactOut(
            window_trading_days=20,
            stock_return_pct=2.5,
            market_contrib_pct=1.0,
            industry_contrib_pct=0.4,
            idio_return_pct=1.1,
            partial=False,
        ),
        pricing=PricingBridgeOut(
            window_label="60d qfq",
            price_change_pct=5.0,
            earnings_contrib_pct=2.0,
            pe_end=20.0,
            partial=True,
            gaps=["pe_start 不可用"],
        ),
    )
    md = report_to_markdown(r)
    assert "## 深度分析 · 影响" in md
    assert "## 深度分析 · 定价桥" in md
    # Impact section present
    assert "2.5" in md
    # Pricing section present
    assert "5.0" in md


def test_markdown_omits_pricing_when_absent() -> None:
    md = report_to_markdown(_mini_report())
    assert "## 深度分析 · 定价桥" not in md


def test_markdown_includes_deep_analysis_thesis_section() -> None:
    from stockresearch.core.schemas import DeepAnalysisOut, ThesisOut

    r = _mini_report()
    r.analysis_depth = "deep"
    r.deep_analysis = DeepAnalysisOut(
        thesis=ThesisOut(
            claim="综合倾向偏多，营收稳健，近期特质收益为正。",
            evidence_ids=["dim:fundamental", "impact:idio"],
            monitors=["补全因子：20日动量", "跟踪因子：净利同比"],
            invalidate_if=["综合评分转弱且倾向转为偏空或中性", "20日动量转负"],
            horizon="20个交易日观察窗",
            partial=False,
        )
    )
    md = report_to_markdown(r)
    assert "## 深度分析 · 研究论点" in md
    assert "综合倾向偏多" in md
    assert "20个交易日观察窗" in md
    assert "dim:fundamental" in md
    assert "impact:idio" in md
    assert "补全因子：20日动量" in md
    assert "20日动量转负" in md


def test_markdown_omits_thesis_when_absent() -> None:
    md = report_to_markdown(_mini_report())
    assert "## 深度分析 · 研究论点" not in md


def test_machine_payload_includes_thesis() -> None:
    from stockresearch.core.schemas import DeepAnalysisOut, ThesisOut

    r = _mini_report()
    r.analysis_depth = "deep"
    r.deep_analysis = DeepAnalysisOut(
        thesis=ThesisOut(
            claim="综合倾向偏多。",
            evidence_ids=["dim:fundamental"],
            monitors=[],
            invalidate_if=[],
            horizon="20个交易日观察窗",
            partial=True,
        )
    )
    payload = report_machine_payload(r)
    assert payload["deep_analysis"]["thesis"]["claim"] == "综合倾向偏多。"
    assert payload["deep_analysis"]["thesis"]["horizon"] == "20个交易日观察窗"
    assert payload["deep_analysis"]["thesis"]["partial"] is True
