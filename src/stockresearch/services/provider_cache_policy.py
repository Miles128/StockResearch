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
    *,
    should_cache: Callable[[dict[str, object]], bool] | None = None,
) -> dict[str, object]:
    """Fetch-through cache. Empty or failed payloads are not persisted by default.

    Pass ``should_cache`` to skip storing unusable shells (e.g. valuation with
    all nulls) so the next request can retry the live provider.
    """
    cached = get_sqlite_cached(cache_key)
    if cached is not None:
        return cached
    result = await fetch()
    if not result:
        return result
    if should_cache is not None and not should_cache(result):
        return result
    if should_cache is None and not should_persist_provider_dict(result):
        return result
    set_sqlite_cached(cache_key, result, ttl_seconds)
    return result


def should_persist_provider_dict(result: dict[str, object]) -> bool:
    """Return False for empty / poison shells that must not occupy TTL cache."""
    if result.get("available") is False:
        return False
    if result.get("signal") == "暂无数据":
        return False

    peers = result.get("peers")
    if isinstance(peers, list) and len(peers) == 0:
        return False

    source = result.get("source")
    if source in (None, "", "none"):
        return False

    if result.get("partial") is True:
        gaps = result.get("gaps")
        if isinstance(gaps, list) and gaps and source in (None, "", "none"):
            return False
        # Incomplete valuation shells (e.g. Tushare PE without percentile) block EM recovery.
        if "tushare" in str(source) and result.get("pe_percentile") is None:
            return False

    return True


def _looks_like_empty_failure(result: dict[str, object]) -> bool:
    """Backward-compatible alias: True means 'do not cache'."""
    return not should_persist_provider_dict(result)
