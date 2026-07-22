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
