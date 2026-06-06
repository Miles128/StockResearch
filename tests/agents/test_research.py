"""Research agent tests."""

import pytest

from stockresearch.agents.research.runner import run_research
from stockresearch.utils.llm import MockLLMClient


@pytest.mark.asyncio
async def test_run_research_four_dimensions() -> None:
    report = await run_research("600519", llm=MockLLMClient())
    assert report.symbol == "600519"
    assert len(report.dimensions) == 4
    assert 1 <= report.composite_score <= 10
    assert report.bias in ("bullish", "bearish", "neutral")
    assert "仅供参考" in report.disclaimer
    assert report.news_text_factor
    assert "新闻文本因子" in report.news_text_factor
    assert report.text_factor_summary
    assert "文本因子·总结" in report.text_factor_summary
    assert report.dimension_weights
