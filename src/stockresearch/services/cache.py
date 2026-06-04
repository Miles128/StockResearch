"""Simple cache with Redis or in-memory fallback (with TTL support)."""

import json
import logging
import time
from typing import Protocol, cast

from stockresearch.core.config import get_settings

logger = logging.getLogger(__name__)

_memory_store: dict[str, tuple[str, float]] = {}
_redis_client: "RedisClient | None" = None

_MEMORY_TTL_SWEEP_INTERVAL = 100
_memory_ops_since_sweep = 0


class RedisClient(Protocol):
    def get(self, key: str) -> str | bytes | None: ...
    def set(self, key: str, value: str) -> None: ...
    def setex(self, key: str, time: int, value: str) -> None: ...
    def ping(self) -> bool: ...


def _get_redis() -> RedisClient | None:
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis

        client = redis.from_url(get_settings().redis_url, decode_responses=True)
        client.ping()
        _redis_client = cast(RedisClient, client)
        return _redis_client
    except Exception:
        logger.debug("Redis unavailable, using in-memory cache")
        return None


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
        client = _get_redis()
        if client is not None:
            result = client.get(key)
            return str(result) if result is not None else None
        entry = _memory_store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at > 0 and time.monotonic() > expires_at:
            del _memory_store[key]
            return None
        return value

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        client = _get_redis()
        if client is not None:
            if ttl_seconds:
                client.setex(key, ttl_seconds, value)
            else:
                client.set(key, value)
            return
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
