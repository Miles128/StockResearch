"""Battle vote tests."""

import pytest

from stockresearch.agents.research.debate import iter_battle_vote_events
from stockresearch.core.schemas import DimensionResult
from stockresearch.services.mock_llm import MockLLMClient


@pytest.mark.asyncio
async def test_battle_vote_collects_dimension_and_side_votes() -> None:
    dimensions = {
        "fundamental": DimensionResult(
            agent="fundamental",
            score=7.0,
            confidence="high",
            highlights=["增长"],
            risks=["估值"],
            data_sources=["mock"],
        ),
        "technical": DimensionResult(
            agent="technical",
            score=4.0,
            confidence="medium",
            highlights=["弱势"],
            risks=["跌破均线"],
            data_sources=["mock"],
        ),
    }
    labels = {"fundamental": "基本面", "technical": "技术面"}
    events: list[dict[str, object]] = []
    async for event in iter_battle_vote_events(
        MockLLMClient(),
        dimensions,
        labels,
        "第1轮看多：测试\n第1轮看空：测试",
    ):
        events.append(event)

    votes = [e for e in events if e.get("type") == "vote"]
    assert len(votes) == 4
    tally = next(e for e in events if e.get("type") == "vote_tally")
    assert (
        int(tally.get("bullish", 0)) + int(tally.get("bearish", 0)) + int(tally.get("neutral", 0))
        == 4
    )
