"""Multi-round debate tests."""

import pytest

from stockresearch.agents.research.debate import run_multi_round_debate
from stockresearch.utils.llm import MockLLMClient


@pytest.mark.asyncio
async def test_multi_round_debate_runs_three_rounds() -> None:
    rounds = await run_multi_round_debate(
        MockLLMClient(),
        "你是看多 Agent。",
        "你是看空 Agent。",
        "标的：贵州茅台(600519)",
    )
    assert len(rounds) == 3
    assert rounds[0].round == 1
    assert rounds[2].round == 3
    assert rounds[0].bull_argument
    assert rounds[0].bear_rebuttal
