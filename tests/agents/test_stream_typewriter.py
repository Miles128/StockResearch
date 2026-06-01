"""Concurrent typewriter stream tests."""

import asyncio

import pytest

from invesbao.agents.stream_typewriter import AgentStreamItem, iter_merged_agent_streams_from_tasks


async def _collect(events_iter) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    async for event in events_iter:
        items.append(event)
    return items


@pytest.mark.asyncio
async def test_merged_streams_start_when_each_task_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "invesbao.agents.stream_typewriter._stream_params",
        lambda: (1, 0.0),
    )

    async def slow() -> AgentStreamItem:
        await asyncio.sleep(0.05)
        return AgentStreamItem("slow", "慢", "analyst", "AAAA")

    async def fast() -> AgentStreamItem:
        return AgentStreamItem("fast", "快", "analyst", "BB")

    tasks = [
        asyncio.create_task(slow()),
        asyncio.create_task(fast()),
    ]
    events = await _collect(iter_merged_agent_streams_from_tasks(tasks))
    deltas = [
        str(event["stream_id"])
        for event in events
        if event["type"] == "text_delta"
    ]
    assert deltas[:2] == ["fast", "fast"]
    assert "slow" in deltas
    done_ids = [str(event["agent_id"]) for event in events if event["type"] == "agent_done"]
    assert done_ids.index("fast") < done_ids.index("slow")
