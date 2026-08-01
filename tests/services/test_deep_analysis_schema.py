from stockresearch.core.schemas import DeepAnalysisOut, ImpactOut, ResearchReportOut


def test_research_report_accepts_deep_analysis() -> None:
    impact = ImpactOut(
        window_trading_days=20,
        stock_return_pct=5.0,
        market_contrib_pct=2.0,
        industry_contrib_pct=1.0,
        idio_return_pct=2.0,
        model="two_step_residual_v1",
        r_squared=0.4,
        market_symbol="000300",
        industry_proxy="peer_ew",
        partial=False,
        gaps=[],
        peak_days=[],
        point_in_time=True,
    )
    report = ResearchReportOut(
        symbol="600519",
        name="贵州茅台",
        dimensions={},
        composite_score=6.0,
        composite_confidence="medium",
        bias="neutral",
        summary="x",
        analysis_depth="deep",
        deep_analysis=DeepAnalysisOut(impact=impact, pricing=None, thesis=None),
    )
    assert report.deep_analysis is not None
    assert report.deep_analysis.impact.market_symbol == "000300"
