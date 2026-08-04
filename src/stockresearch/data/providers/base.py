"""Shared data-provider helpers to remove repeated mock/timeout/fallback code."""

import asyncio
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)
_RAISE = object()


async def run_sync_fetch[T](
    name: str,
    fn: Callable[[], T],
    *,
    timeout: float,
    fallback: Callable[[], T] | T | None | object = _RAISE,
) -> T | None:
    """Run a synchronous fetch function in a thread with timeout and fallback."""
    try:
        return await asyncio.wait_for(asyncio.to_thread(fn), timeout=timeout)
    except Exception as exc:
        logger.warning("%s failed: %s", name, exc)
        if fallback is _RAISE:
            raise
        if callable(fallback):
            return fallback()
        return fallback
