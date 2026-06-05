"""Simple in-process TTL cache for slow external data fetches."""

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

_store: dict[str, tuple[float, object]] = {}


def get_cached(key: str, ttl_sec: float, factory: Callable[[], T]) -> T:
    now = time.monotonic()
    entry = _store.get(key)
    if entry is not None and now - entry[0] < ttl_sec:
        return entry[1]  # type: ignore[return-value]
    value = factory()
    _store[key] = (now, value)
    return value


def clear_cache() -> None:
    _store.clear()
