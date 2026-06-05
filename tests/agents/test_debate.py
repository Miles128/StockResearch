"""Debate agent tests."""

import pytest

from stockresearch.agents.research.debate import _format_debate_utterance, run_debate
from stockresearch.core.schemas import DimensionResult
from stockresearch.utils.llm import MockLLMClient


def test_format_debate_utterance_adds_summary_marker() -> None:
    formatted = _format_debate_utterance("估值合理，盈利稳健。但增速放缓需关注。")
    assert "【摘要】" in formatted
    assert "【详述】" in formatted


def test_format_debate_utterance_does_not_truncate_long_text() -> None:
    long_body = "第一句论点。" + "补充论据。" * 80
    formatted = _format_debate_utterance(long_body)
    assert "…" not in formatted
    assert len(formatted) > 220


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
