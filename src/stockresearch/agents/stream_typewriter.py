"""Emit SSE text_delta events after content is ready (typewriter display)."""

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from stockresearch.core.config import get_settings
from stockresearch.core.schemas import DimensionResult
from stockresearch.i18n.status_events import status_event
from stockresearch.utils.llm import LLMClient

logger = logging.getLogger(__name__)

_CHARS_PER_DELTA = 1
_DELAY_SEC = 0.0
_PUMP_DONE = object()
_PREPARE_TIMEOUT_SEC = 120.0


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
    """Stream LLM tokens into queue as text_delta + agent_done.

    Guarantees a ``_PUMP_DONE`` sentinel is emitted even when the underlying
    LLM stream raises, so the merged iterator never hangs.
    """
    content = ""
    done_emitted = False
    try:
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
                done_emitted = True
    except Exception as exc:
        logger.warning("LLM stream pump failed for agent %s: %s", agent_id, exc)
        if not done_emitted:
            content = content or f"{agent_name}输出中断，请稍后重试。"
            await queue.put(
                {
                    "type": "agent_done",
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "role": role,
                    "content": content,
                }
            )
    finally:
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
    await queue.put(
        {
            "type": "agent_start",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "role": "analyst",
        }
    )
    await queue.put(status_event("status.research.fetch_data", agent=agent_name))

    async def _emit_unavailable() -> None:
        content = f"{agent_name}数据暂不可用，请稍后重试。"
        dim = DimensionResult(
            agent=agent_id,
            score=5.0,
            confidence="low",
            highlights=[content],
            risks=[],
            data_sources=[],
        )
        dimensions[agent_id] = dim
        await queue.put(
            {
                "type": "dimension_ready",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "role": "analyst",
                "content": content,
                "dimension": dim.model_dump(mode="json"),
            }
        )
        await queue.put(
            {
                "type": "agent_done",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "role": "analyst",
                "content": content,
            }
        )

    try:
        try:
            system, user, data = await asyncio.wait_for(
                prepare(ctx),  # type: ignore[operator]
                timeout=_PREPARE_TIMEOUT_SEC,
            )
        except Exception as exc:
            logger.warning("Dimension %s prepare failed: %s", agent_id, exc)
            await _emit_unavailable()
            return

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
        from stockresearch.utils.disclaimer import strip_disclaimer

        analysis = strip_disclaimer("".join(parts))
        dim = build(data, analysis)  # type: ignore[operator]
        dimensions[agent_id] = dim
        content = analysis.strip() or analysis
        await queue.put(
            {
                "type": "dimension_ready",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "role": "analyst",
                "content": content,
                "dimension": dim.model_dump(mode="json"),  # type: ignore[union-attr]
            }
        )
        await queue.put(
            {
                "type": "agent_done",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "role": "analyst",
                "content": content,
            }
        )
    except Exception as exc:
        logger.warning("Dimension %s stream/build failed: %s", agent_id, exc)
        await _emit_unavailable()
    finally:
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
        try:
            item = await task
        except Exception:
            logger.warning("Merged agent stream task failed", exc_info=True)
            # Still emit a done marker so the merged iterator terminates.
            await queue.put(_PUMP_DONE)
            return
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
