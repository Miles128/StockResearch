"""Research streaming tests."""

import pytest

from stockresearch.agents.research.stream import run_research_stream
from stockresearch.utils.llm import MockLLMClient


@pytest.mark.asyncio
async def test_research_stream_emits_agents_debate_and_report() -> None:
    events: list[dict[str, object]] = []
    async for event in run_research_stream("600519", llm=MockLLMClient()):
        events.append(event)

    types = [str(e.get("type")) for e in events]
    assert types.count("agent_start") >= 7
    assert types.count("debate_round") == 3
    assert any(e.get("type") == "vote_tally" for e in events)
    assert any(e.get("type") == "manager" for e in events)
    assert "judge" in types
    assert types[-1] == "done"
    result = events[-1].get("result")
    assert isinstance(result, dict)
    assert result.get("symbol") == "600519"
