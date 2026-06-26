"""Shared data-provider helpers to remove repeated mock/timeout/fallback code."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")
_RAISE = object()


async def run_sync_fetch(
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


async def run_async_fetch(
    name: str,
    coro_factory: Callable[[], Awaitable[T]],
    *,
    timeout: float,
    fallback: Callable[[], Awaitable[T]] | T | None | object = _RAISE,
) -> T | None:
    """Run an async fetch coroutine with timeout and fallback."""
    try:
        return await asyncio.wait_for(coro_factory(), timeout=timeout)
    except Exception as exc:
        logger.warning("%s failed: %s", name, exc)
        if fallback is _RAISE:
            raise
        if callable(fallback):
            return await fallback()
        return fallback
