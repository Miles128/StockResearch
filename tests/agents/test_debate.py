"""Debate agent tests."""

import pytest

from invesbao.agents.research.debate import run_debate
from invesbao.core.schemas import DimensionResult
from invesbao.utils.llm import MockLLMClient


@pytest.mark.asyncio
async def test_run_debate() -> None:
    dimensions = {
        "fundamental": DimensionResult(
            agent="fundamental",
            score=7.0,
            confidence="high",
            highlights=["营收增长"],
            risks=["估值偏高"],
            data_sources=["akshare"],
        ),
        "technical": DimensionResult(
            agent="technical",
            score=6.0,
            confidence="medium",
            highlights=["均线多头"],
            risks=["RSI偏高"],
            data_sources=["akshare"],
        ),
    }
    result = await run_debate("600519", "贵州茅台", dimensions, MockLLMClient())
    assert len(result.rounds) == 3
    assert result.final_bias in ("bullish", "bearish", "neutral")
    assert result.judge_verdict
