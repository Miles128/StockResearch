"""ReAct should not return empty apology when research cards exist."""

from stockresearch.agents.orchestrator.react_agent import _reply_from_cards


def test_reply_from_research_card() -> None:
    reply = _reply_from_cards(
        [
            {
                "type": "research",
                "data": {
                    "symbol": "600030",
                    "name": "中信证券",
                    "composite_score": 6.8,
                    "summary": "中信证券综合偏多，情绪面改善。",
                },
            }
        ]
    )
    assert reply == "中信证券综合偏多，情绪面改善。"
