"""Simple cache with Redis or in-memory fallback."""

import json
import logging
from typing import Protocol, cast

from invesbao.core.config import get_settings

logger = logging.getLogger(__name__)

_memory_store: dict[str, str] = {}
_redis_client: "RedisClient | None" = None


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


class CacheService:
    def get(self, key: str) -> str | None:
        client = _get_redis()
        if client is not None:
            result = client.get(key)
            return str(result) if result is not None else None
        return _memory_store.get(key)

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        client = _get_redis()
        if client is not None:
            if ttl_seconds:
                client.setex(key, ttl_seconds, value)
            else:
                client.set(key, value)
            return
        _memory_store[key] = value

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
