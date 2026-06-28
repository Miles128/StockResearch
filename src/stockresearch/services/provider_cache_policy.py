"""TTL policy and helpers for SQLite-backed provider cache."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from stockresearch.core.schemas import ModeSettingsOut
from stockresearch.data.provider_meta import get_provider_meta
from stockresearch.services.sqlite_cache import get_sqlite_cached, set_sqlite_cached

DEFAULT_QUOTE_CACHE_TTL_SECONDS = 600
DAILY_CACHE_TTL_SECONDS = 86400

T = TypeVar("T")


def quote_cache_ttl_seconds(settings: ModeSettingsOut | None = None) -> int:
    """Quote cache TTL; user setting overrides default 10 minutes."""
    if settings is not None:
        minutes = getattr(settings, "quote_refresh_minutes", 10) or 10
        return max(1, min(120, int(minutes))) * 60
    return DEFAULT_QUOTE_CACHE_TTL_SECONDS


def provider_ttl(provider_key: str, *, fallback: int = DAILY_CACHE_TTL_SECONDS) -> int:
    meta = get_provider_meta(provider_key)
    if meta and meta.default_ttl_seconds:
        return meta.default_ttl_seconds
    return fallback


async def get_or_set_cached_dict(
    cache_key: str,
    ttl_seconds: int,
    fetch: Callable[[], Awaitable[dict[str, object]]],
) -> dict[str, object]:
    cached = get_sqlite_cached(cache_key)
    if cached is not None:
        return cached
    result = await fetch()
    if result:
        set_sqlite_cached(cache_key, result, ttl_seconds)
    return result
