"""Streaming master commentary for research / industry / risk reports."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from stockresearch.agents.master_commentary.prompts import MASTER_CONFIG
from stockresearch.agents.master_commentary.schemas import MasterCommentaryOut
from stockresearch.utils.llm import LLMClient


async def _fetch_master(
    llm: LLMClient,
    master_id: str,
    context: str,
) -> MasterCommentaryOut:
    config = MASTER_CONFIG[master_id]
    try:
        raw = await llm.complete(config["system"], context)
    except Exception as exc:
        return MasterCommentaryOut(
            master=master_id,
            signal="neutral",
            confidence=0.0,
            reasoning=f"点评生成失败：{exc}",
            key_metric="",
        )
    return MasterCommentaryOut.from_llm(master_id, raw)


async def stream_master_commentary(
    llm: LLMClient,
    subject: str,
    context: str,
    *,
    masters: list[str] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield master_start, master_done, and a final master_commentary list event."""
    master_ids = masters or list(MASTER_CONFIG.keys())

    yield {"type": "master_start", "subject": subject, "masters": master_ids}

    queue: asyncio.Queue[MasterCommentaryOut] = asyncio.Queue()

    async def pump(master_id: str) -> None:
        result = await _fetch_master(llm, master_id, context)
        await queue.put(result)

    pumps = [asyncio.create_task(pump(mid)) for mid in master_ids]
    results: list[MasterCommentaryOut] = []

    for _ in master_ids:
        result = await queue.get()
        results.append(result)
        yield {
            "type": "master_done",
            "master": result.master,
            "name": MASTER_CONFIG[result.master]["name"],
            "signal": result.signal,
            "signal_text": result.signal_text,
            "confidence": result.confidence,
            "reasoning": result.reasoning,
            "key_metric": result.key_metric,
        }

    await asyncio.gather(*pumps)

    yield {
        "type": "master_commentary",
        "subject": subject,
        "commentary": [r.model_dump(mode="json") for r in results],
    }


async def get_master_commentary(
    llm: LLMClient,
    subject: str,
    context: str,
    *,
    masters: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Non-streaming convenience wrapper returning the commentary list."""
    commentary: list[dict[str, Any]] = []
    async for event in stream_master_commentary(llm, subject, context, masters=masters):
        if event.get("type") == "master_commentary" and isinstance(event.get("commentary"), list):
            commentary = event["commentary"]
    return commentary
