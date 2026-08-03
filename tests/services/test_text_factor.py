"""Text factor compression tests."""

from stockresearch.core.schemas import DimensionResult
from stockresearch.services.text_factor import (
    NewsSnippet,
    build_dimension_text_factor,
    build_news_text_factor,
    build_text_factor_summary,
    news_from_title,
)


def test_build_news_text_factor_groups_and_sentiment() -> None:
    items = [
        NewsSnippet(title="龙头业绩超预期", sentiment="bullish", category="holding"),
        NewsSnippet(title="板块政策收紧", sentiment="bearish", category="sector"),
        NewsSnippet(title="指数震荡整理", sentiment="neutral", category="market"),
    ]
    text = build_news_text_factor(items, subject="测试标的")
    assert "新闻文本因子" in text
    assert "持仓相关" in text
    assert "龙头业绩超预期" in text
    assert "偏多 1" in text


def test_build_news_text_factor_from_titles() -> None:
    text = build_news_text_factor(
        [news_from_title("新能源补贴延续"), news_from_title("光伏装机新高")],
        subject="新能源",
    )
    assert "新能源" in text
    assert "光伏装机新高" in text


def test_build_text_factor_summary_includes_weights() -> None:
    dimensions = {
        "fundamental": DimensionResult(
            agent="基本面",
            score=7.0,
            confidence="high",
            highlights=["盈利改善"],
            risks=[],
            data_sources=["财报"],
        ),
        "technical": DimensionResult(
            agent="技术面",
            score=5.0,
            confidence="low",
            highlights=["均线纠缠"],
            risks=["量能不足"],
            data_sources=[],
        ),
    }
    summary = build_text_factor_summary(
        subject="测试股",
        dimensions=dimensions,
        dimension_labels={"fundamental": "基本面", "technical": "技术面"},
        composite_score=6.2,
        composite_confidence="medium",
        dimension_weights={"fundamental": 1.05, "technical": 0.5},
        news_text_factor="【测试 · 新闻文本因子】暂无。",
        debate_consensus="分歧中等",
    )
    assert "文本因子·总结" in summary
    assert "维度权重" in summary
    assert "投研维度因子" in summary
    assert "新闻文本因子" in summary
    assert "多空合议" in summary


def test_build_dimension_text_factor_lists_highlights() -> None:
    dim = DimensionResult(
        agent="情绪面",
        score=6.5,
        confidence="medium",
        highlights=["舆情回暖"],
        risks=["解禁压力"],
        data_sources=[],
    )
    text = build_dimension_text_factor({"sentiment": dim}, {"sentiment": "情绪面"})
    assert "情绪面" in text
    assert "舆情回暖" in text
