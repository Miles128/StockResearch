"""Risk streaming multi-agent tests."""

import pytest

from stockresearch.agents.risk.stream import run_risk_checkup_stream
from stockresearch.db.models import Holding
from stockresearch.utils.llm import MockLLMClient


async def _collect_events(holdings: list[Holding]) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    async for event in run_risk_checkup_stream(holdings, llm=MockLLMClient()):
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_stream_emits_parallel_agents_and_debate() -> None:
    holdings = [
        Holding(
            id=1,
            user_id=1,
            symbol="300750",
            name="宁德时代",
            cost_price=250.0,
            quantity=100,
            sector="新能源",
        ),
        Holding(
            id=2,
            user_id=1,
            symbol="600519",
            name="贵州茅台",
            cost_price=1800.0,
            quantity=10,
            sector="白酒",
        ),
    ]
    events = await _collect_events(holdings)
    types = [str(e.get("type")) for e in events]
    assert types.count("agent_start") >= 6
    assert types.count("debate_round") == 3
    debate_events = [e for e in events if e.get("type") == "debate_round"]
    assert debate_events[0].get("aggressive")
    assert debate_events[0].get("neutral_view")
    assert debate_events[0].get("conservative")
    judge_events = [e for e in events if e.get("type") == "judge"]
    assert judge_events
    assert judge_events[0].get("position_action") in ("加仓", "减仓", "持有观望")
    assert judge_events[0].get("risk_level") in ("低", "中", "高")
    holding_actions = judge_events[0].get("holding_actions")
    assert isinstance(holding_actions, list)
    assert len(holding_actions) == len(holdings)
    assert judge_events[0].get("analysis_process")
    assert types[-1] == "done"


@pytest.mark.asyncio
async def test_stream_empty_holdings_still_finishes() -> None:
    events = await _collect_events([])
    assert events[-1]["type"] == "done"
    assert "result" in events[-1]
