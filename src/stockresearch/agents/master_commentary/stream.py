"""Streaming master commentary for research / industry / risk reports."""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from stockresearch.agents.master_commentary.registry import get_master_config, to_commentary_payload
from stockresearch.agents.master_commentary.schemas import MasterCommentaryOut
from stockresearch.core.schemas import ModeSettingsOut
from stockresearch.utils.llm import LLMClient

logger = logging.getLogger(__name__)


async def _fetch_master(
    llm: LLMClient,
    master_id: str,
    context: str,
    settings: ModeSettingsOut,
) -> MasterCommentaryOut:
    try:
        config = get_master_config(master_id, settings)
        raw = await llm.complete(config["system"], context)
    except Exception as exc:
        logger.warning("master commentary failed for %s: %s", master_id, exc, exc_info=True)
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
    settings: ModeSettingsOut,
    masters: list[str] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield master_start, master_done, and a final master_commentary list event."""
    master_ids = masters or []
    if not master_ids:
        return

    yield {"type": "master_start", "subject": subject, "masters": master_ids}

    queue: asyncio.Queue[MasterCommentaryOut] = asyncio.Queue()

    async def pump(master_id: str) -> None:
        result = await _fetch_master(llm, master_id, context, settings)
        await queue.put(result)

    pumps = [asyncio.create_task(pump(mid)) for mid in master_ids]
    results: list[MasterCommentaryOut] = []

    for _ in master_ids:
        result = await queue.get()
        results.append(result)
        payload = to_commentary_payload(result, settings)
        yield {"type": "master_done", **payload}

    await asyncio.gather(*pumps)

    yield {
        "type": "master_commentary",
        "subject": subject,
        "commentary": [to_commentary_payload(result, settings) for result in results],
    }


async def get_master_commentary(
    llm: LLMClient,
    subject: str,
    context: str,
    *,
    settings: ModeSettingsOut,
    masters: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Non-streaming convenience wrapper returning the commentary list."""
    commentary: list[dict[str, Any]] = []
    async for event in stream_master_commentary(
        llm, subject, context, settings=settings, masters=masters
    ):
        if event.get("type") == "master_commentary" and isinstance(event.get("commentary"), list):
            commentary = event["commentary"]
    return commentary
