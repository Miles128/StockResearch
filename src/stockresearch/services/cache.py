"""In-memory cache with TTL support."""

import json
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

_memory_store: dict[str, tuple[str, float]] = {}
_factory_store: dict[str, tuple[float, object]] = {}

_MEMORY_TTL_SWEEP_INTERVAL = 100
_memory_ops_since_sweep = 0


def _sweep_expired() -> None:
    global _memory_ops_since_sweep
    _memory_ops_since_sweep += 1
    if _memory_ops_since_sweep < _MEMORY_TTL_SWEEP_INTERVAL:
        return
    _memory_ops_since_sweep = 0
    now = time.monotonic()
    expired = [k for k, (_, exp) in _memory_store.items() if exp > 0 and now > exp]
    for k in expired:
        del _memory_store[k]


class CacheService:
    def get(self, key: str) -> str | None:
        entry = _memory_store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at > 0 and time.monotonic() > expires_at:
            del _memory_store[key]
            return None
        return value

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        expires_at = 0.0
        if ttl_seconds:
            expires_at = time.monotonic() + ttl_seconds
        _memory_store[key] = (value, expires_at)
        _sweep_expired()

    def get_json(self, key: str) -> dict[str, object] | None:
        raw = self.get(key)
        if raw is None:
            return None
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
        return None

    def set_json(self, key: str, value: dict[str, object], ttl_seconds: int | None = None) -> None:
        self.set(key, json.dumps(value, ensure_ascii=False), ttl_seconds)

    def clear_memory(self) -> None:
        _memory_store.clear()
        _factory_store.clear()


def get_cached(key: str, ttl_sec: float, factory: Callable[[], T]) -> T:
    now = time.monotonic()
    entry = _factory_store.get(key)
    if entry is not None and now - entry[0] < ttl_sec:
        return entry[1]  # type: ignore[return-value]
    value = factory()
    _factory_store[key] = (now, value)
    return value


def clear_cache() -> None:
    _memory_store.clear()
    _factory_store.clear()
