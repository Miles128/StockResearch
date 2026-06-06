"""Plan-Execute should surface research cards from tool calls."""

from stockresearch.agents.orchestrator.stream import _merge_plan_cards


def test_merge_plan_cards_attaches_research() -> None:
    plan_cards = [
        {"type": "plan", "data": {"phase": "plan", "steps": []}},
        {"type": "plan", "data": {"phase": "synthesis", "step_count": 3}},
    ]
    tool_cards = [
        {
            "type": "research",
            "data": {
                "symbol": "600519",
                "name": "贵州茅台",
                "composite_score": 7.2,
                "dimensions": {"fundamental": {"score": 7}},
            },
        }
    ]
    merged = _merge_plan_cards(plan_cards, tool_cards)
    types = [c["type"] for c in merged]
    assert "research" in types
    research = next(c for c in merged if c["type"] == "research")
    assert research["data"]["symbol"] == "600519"
