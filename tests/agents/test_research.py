"""Research agent tests."""

import pytest

from invesbao.agents.research.runner import run_research
from invesbao.utils.llm import MockLLMClient


@pytest.mark.asyncio
async def test_run_research_four_dimensions() -> None:
    report = await run_research("600519", llm=MockLLMClient())
    assert report.symbol == "600519"
    assert len(report.dimensions) == 4
    assert 1 <= report.composite_score <= 10
    assert report.bias in ("bullish", "bearish", "neutral")
    assert "仅供参考" in report.disclaimer
