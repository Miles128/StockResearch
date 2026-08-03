"""Tests for dimension analysis parsing and brief summary."""

from stockresearch.agents.research.dimension_text import (
    build_brief_summary,
    finalize_dimension,
    parse_dimension_analysis,
)
from stockresearch.core.schemas import DimensionResult, ResearchReportOut
from stockresearch.services.report_export import report_to_markdown


def test_parse_marked_sections() -> None:
    raw = (
        "【分析】营收稳健，ROE 仍处高位，估值略贵但现金流好。\n"
        "【亮点】盈利能力强；品牌护城河深\n"
        "【风险】估值偏高；消费复苏节奏不确定"
    )
    analysis, highlights, risks = parse_dimension_analysis(raw)
    assert "营收稳健" in analysis
    assert "盈利能力强" in highlights
    assert "估值偏高" in risks


def test_parse_unmarked_falls_back_to_full_text() -> None:
    raw = "价格站上均线。风险在于成交量萎缩。"
    analysis, highlights, risks = parse_dimension_analysis(raw)
    assert analysis.startswith("价格站上均线")
    assert any("风险" in r for r in risks) or risks == []


def test_finalize_uses_fallbacks() -> None:
    dim = finalize_dimension(
        agent="technical",
        score=6.5,
        confidence="medium",
        raw_analysis="",
        data_sources=["akshare_kline"],
        fallback_highlights=["RSI 55"],
        fallback_risks=["支撑参考 MA20"],
    )
    assert dim.analysis
    assert dim.highlights == ["RSI 55"]
    assert dim.risks == ["支撑参考 MA20"]


def test_brief_summary_plain_language() -> None:
    dims = {
        "fundamental": DimensionResult(
            agent="fundamental",
            score=7.0,
            confidence="high",
            analysis="公司赚钱能力很强。",
            highlights=["赚钱能力很强"],
            risks=["估值不便宜"],
            data_sources=[],
        )
    }
    brief = build_brief_summary(
        name="贵州茅台",
        symbol="600519",
        bias="bullish",
        composite_score=7.2,
        dimensions=dims,
        dimension_labels={"fundamental": "基本面"},
    )
    assert "偏乐观" in brief
    assert "基本面看" in brief


def test_report_markdown_uses_dimension_section_not_fixed_four() -> None:
    report = ResearchReportOut(
        symbol="600519",
        name="贵州茅台",
        dimensions={
            "fundamental": DimensionResult(
                agent="fundamental",
                score=7.5,
                confidence="high",
                analysis="盈利稳健，现金流充裕。",
                highlights=["盈利稳健"],
                risks=["估值偏高"],
                data_sources=["akshare_financials"],
            )
        },
        composite_score=7.5,
        composite_confidence="high",
        bias="bullish",
        summary="贵州茅台综合偏多。",
        brief_summary="贵州茅台整体偏乐观。",
    )
    md = report_to_markdown(report)
    assert "维度分析（1）" in md
    assert "四维分析" not in md
    assert "盈利稳健，现金流充裕" in md
