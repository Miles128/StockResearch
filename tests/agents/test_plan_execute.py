"""Plan-and-Execute step normalization."""

from stockresearch.agents.orchestrator.plan_execute import _normalize_plan_steps


def test_market_query_expands_single_step_plan() -> None:
    shallow = [
        {
            "id": 1,
            "description": "获取大盘数据",
            "tool": "get_market_data",
            "args": {},
        }
    ]
    steps = _normalize_plan_steps("今日A股大盘走势怎么样", shallow)
    assert len(steps) >= 3
    tools = [s["tool"] for s in steps]
    assert "get_market_data" in tools
    assert "get_news" in tools
    assert tools[-1] == "auto"


def test_stock_query_expands_to_multi_step() -> None:
    shallow = [
        {
            "id": 1,
            "description": "分析茅台",
            "tool": "get_stock_research",
            "args": {"symbol": "600519"},
        }
    ]
    steps = _normalize_plan_steps("帮我分析一下600519", shallow)
    assert len(steps) >= 3
    assert any(s["tool"] == "get_news" for s in steps)


def test_already_rich_plan_unchanged() -> None:
    rich = [
        {"id": 1, "tool": "get_market_data", "args": {}, "description": "a"},
        {"id": 2, "tool": "get_news", "args": {}, "description": "b"},
        {"id": 3, "tool": "auto", "args": {}, "description": "c"},
    ]
    steps = _normalize_plan_steps("对比新能源和半导体板块前景", rich)
    assert len(steps) == 3
    assert steps[0]["description"] == "a"
