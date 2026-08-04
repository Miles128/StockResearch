"""Risk streaming multi-agent tests."""

from datetime import UTC, datetime

import pytest

from stockresearch.agents.risk.stream import run_risk_checkup_stream
from stockresearch.data.providers.market import Quote, QuoteProvider
from stockresearch.db.models import Holding
from stockresearch.services.mock_llm import MockLLMClient


def _fake_quotes(symbols: list[str]) -> dict[str, Quote]:
    names = {"300750": "宁德时代", "600519": "贵州茅台"}
    return {
        sym: Quote(
            symbol=sym,
            name=names.get(sym, sym),
            price=200.0 if sym == "300750" else 1800.0,
            change_pct=-2.0,
            open=200.0,
            high=210.0,
            low=198.0,
            volume=10000.0,
            updated_at=datetime.now(UTC),
        )
        for sym in symbols
    }


async def _collect_events(
    holdings: list[Holding], monkeypatch: pytest.MonkeyPatch
) -> list[dict[str, object]]:
    async def fake_get_quotes(self, symbols: list[str], **kwargs: object) -> dict[str, Quote]:
        return _fake_quotes(symbols)

    monkeypatch.setattr(QuoteProvider, "get_quotes", fake_get_quotes)
    events: list[dict[str, object]] = []
    async for event in run_risk_checkup_stream(holdings, llm=MockLLMClient()):
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_stream_emits_parallel_agents_and_debate(monkeypatch: pytest.MonkeyPatch) -> None:
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
    events = await _collect_events(holdings, monkeypatch)
    types = [str(e.get("type")) for e in events]
    assert "risk_snapshot" in types
    assert types.count("agent_start") >= 6
    assert types.count("debate_round") == 1
    debate_events = [e for e in events if e.get("type") == "debate_round"]
    assert debate_events[0].get("aggressive")
    assert debate_events[0].get("neutral_view")
    assert debate_events[0].get("conservative")
    judge_events = [e for e in events if e.get("type") == "judge"]
    assert judge_events
    assert judge_events[0].get("position_action") in (
        "仓位偏高",
        "仓位偏低",
        "仓位适中",
        "建议控制仓位",
    )
    assert judge_events[0].get("risk_level") in ("低", "中", "高")
    holding_actions = judge_events[0].get("holding_actions")
    assert isinstance(holding_actions, list)
    assert len(holding_actions) == len(holdings)
    assert judge_events[0].get("analysis_process")
    assert types[-1] == "done"


@pytest.mark.asyncio
async def test_stream_empty_holdings_still_finishes(monkeypatch: pytest.MonkeyPatch) -> None:
    events = await _collect_events([], monkeypatch)
    assert events[-1]["type"] == "done"
    assert "result" in events[-1]
