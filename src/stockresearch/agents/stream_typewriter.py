"""Emit SSE text_delta events after content is ready (typewriter display)."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

from stockresearch.core.config import get_settings
from stockresearch.utils.llm import LLMClient

_CHARS_PER_DELTA = 1
_DELAY_SEC = 0.0
_PUMP_DONE = object()


@dataclass(frozen=True)
class AgentStreamItem:
    agent_id: str
    agent_name: str
    role: str
    content: str
    stream_id: str | None = None


def _stream_params() -> tuple[int, float]:
    if get_settings().use_mock_llm:
        return 9999, 0.0
    return _CHARS_PER_DELTA, _DELAY_SEC


async def iter_text_deltas(
    stream_id: str,
    text: str,
) -> AsyncIterator[dict[str, object]]:
    chunk_size, delay = _stream_params()
    if not text:
        return
    for offset in range(0, len(text), chunk_size):
        yield {
            "type": "text_delta",
            "stream_id": stream_id,
            "delta": text[offset : offset + chunk_size],
        }
        if delay > 0:
            await asyncio.sleep(delay)


async def iter_llm_stream_events(
    *,
    stream_id: str,
    agent_id: str,
    agent_name: str,
    role: str,
    llm: LLMClient,
    system: str,
    user: str,
) -> AsyncIterator[dict[str, object]]:
    """Stream LLM tokens as text_delta events, then agent_done."""
    parts: list[str] = []
    async for chunk in llm.stream_complete(system, user):
        parts.append(chunk)
        yield {
            "type": "text_delta",
            "stream_id": stream_id,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "role": role,
            "delta": chunk,
        }
    content = "".join(parts)
    yield {
        "type": "agent_done",
        "agent_id": agent_id,
        "agent_name": agent_name,
        "role": role,
        "content": content,
    }


async def pump_llm_stream_events_to_queue(
    queue: asyncio.Queue[object],
    *,
    stream_id: str,
    agent_id: str,
    agent_name: str,
    role: str,
    llm: LLMClient,
    system: str,
    user: str,
) -> str:
    """Stream LLM tokens into queue as text_delta + agent_done."""
    content = ""
    async for event in iter_llm_stream_events(
        stream_id=stream_id,
        agent_id=agent_id,
        agent_name=agent_name,
        role=role,
        llm=llm,
        system=system,
        user=user,
    ):
        await queue.put(event)
        if event.get("type") == "agent_done":
            content = str(event.get("content", ""))
    await queue.put(_PUMP_DONE)
    return content


async def pump_dimension_llm_stream(
    queue: asyncio.Queue[object],
    *,
    ctx: object,
    agent_id: str,
    agent_name: str,
    prepare: object,
    build: object,
    dimensions: dict[str, object],
) -> None:
    """Fetch market data, stream LLM analysis, store DimensionResult."""
    system, user, data = await prepare(ctx)  # type: ignore[operator]
    parts: list[str] = []
    async for chunk in ctx.llm.stream_complete(system, user):  # type: ignore[attr-defined]
        parts.append(chunk)
        await queue.put(
            {
                "type": "text_delta",
                "stream_id": agent_id,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "role": "analyst",
                "delta": chunk,
            }
        )
    analysis = "".join(parts)
    dim = build(data, analysis)  # type: ignore[operator]
    dimensions[agent_id] = dim
    await queue.put(
        {
            "type": "agent_done",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "role": "analyst",
            "content": analysis.strip() or analysis,
        }
    )
    await queue.put(_PUMP_DONE)


async def iter_agent_done_stream(
    *,
    agent_id: str,
    agent_name: str,
    role: str,
    content: str,
    stream_id: str | None = None,
) -> AsyncIterator[dict[str, object]]:
    sid = stream_id or agent_id
    async for event in iter_text_deltas(sid, content):
        yield event
    yield {
        "type": "agent_done",
        "agent_id": agent_id,
        "agent_name": agent_name,
        "role": role,
        "content": content,
    }


async def pump_agent_done_stream(
    queue: asyncio.Queue[object],
    *,
    agent_id: str,
    agent_name: str,
    role: str,
    content: str,
    stream_id: str | None = None,
) -> None:
    async for event in iter_agent_done_stream(
        agent_id=agent_id,
        agent_name=agent_name,
        role=role,
        content=content,
        stream_id=stream_id,
    ):
        await queue.put(event)
    await queue.put(_PUMP_DONE)


async def iter_queue_merged_events(
    queue: asyncio.Queue[object],
    pump_count: int,
) -> AsyncIterator[dict[str, object]]:
    finished = 0
    while finished < pump_count:
        item = await queue.get()
        if item is _PUMP_DONE:
            finished += 1
            continue
        yield item  # type: ignore[misc]


async def iter_merged_agent_streams_from_tasks(
    tasks: list[asyncio.Task[AgentStreamItem]],
) -> AsyncIterator[dict[str, object]]:
    """Start typing each agent as soon as its analysis task finishes."""
    if not tasks:
        return
    if len(tasks) == 1:
        item = await tasks[0]
        async for event in iter_agent_done_stream(
            agent_id=item.agent_id,
            agent_name=item.agent_name,
            role=item.role,
            content=item.content,
            stream_id=item.stream_id,
        ):
            yield event
        return

    queue: asyncio.Queue[object] = asyncio.Queue()
    pumps: list[asyncio.Task[None]] = []

    async def when_ready(task: asyncio.Task[AgentStreamItem]) -> None:
        item = await task
        await pump_agent_done_stream(
            queue,
            agent_id=item.agent_id,
            agent_name=item.agent_name,
            role=item.role,
            content=item.content,
            stream_id=item.stream_id,
        )

    for task in tasks:
        pumps.append(asyncio.create_task(when_ready(task)))

    async for event in iter_queue_merged_events(queue, len(tasks)):
        yield event

    await asyncio.gather(*pumps)
