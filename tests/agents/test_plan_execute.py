"""Plan-and-Execute step normalization."""

import pytest

from stockresearch.agents.orchestrator.plan_execute import PlanExecuteAgent, _normalize_plan_steps
from stockresearch.utils.llm import LLMClient


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


class _FakeLLM(LLMClient):
    """Planning returns a 3-step JSON plan; everything else a canned summary."""

    async def complete(self, system: str, user: str) -> str:
        if "规划 Agent" in system and "complexity" not in system:
            return (
                '```json\n{"reasoning": "测试计划", "steps": ['
                '{"id": 1, "description": "获取大盘数据", "tool": "get_market_data", "args": {}},'
                '{"id": 2, "description": "获取新闻", "tool": "get_news", "args": {}},'
                '{"id": 3, "description": "综合结论", "tool": "auto", "args": {}}'
                "]}\n```"
            )
        return "综合结论：测试完成。"


async def _fake_tool_executor(name: str, args: dict) -> str:
    return f"工具 {name} 返回：测试数据"


@pytest.mark.asyncio
async def test_plan_execute_run_end_to_end_no_format_crash() -> None:
    """Regression: _PLAN_SYSTEM.format() must not raise KeyError on JSON braces."""
    agent = PlanExecuteAgent(llm=_FakeLLM(), tool_executor=_fake_tool_executor, finance_tools=True)
    reply, cards = await agent.run("今日A股大盘走势怎么样")
    assert "测试完成" in reply
    phases = [c["data"]["phase"] for c in cards]
    assert "plan" in phases
    assert "execute" in phases
    assert "synthesis" in phases
    assert len(agent._plan_steps) >= 3


@pytest.mark.asyncio
async def test_plan_execute_general_path() -> None:
    """Non-finance path uses _PLAN_GENERAL_SYSTEM (no tools_block placeholder)."""
    agent = PlanExecuteAgent(llm=_FakeLLM(), tool_executor=_fake_tool_executor, finance_tools=False)
    reply, cards = await agent.run("帮我写一段 Python 冒泡排序")
    assert reply
    assert any(c["data"]["phase"] == "plan" for c in cards)
