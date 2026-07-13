"""Tests for provider cache TTL policy."""

import pytest

from stockresearch.core.schemas import ModeSettingsOut
from stockresearch.db.session import init_db
from stockresearch.services.provider_cache_policy import (
    DEFAULT_QUOTE_CACHE_TTL_SECONDS,
    get_or_set_cached_dict,
    quote_cache_ttl_seconds,
)
from stockresearch.services.sqlite_cache import get_sqlite_cached


def test_quote_cache_ttl_default() -> None:
    assert quote_cache_ttl_seconds(None) == DEFAULT_QUOTE_CACHE_TTL_SECONDS


def test_quote_cache_ttl_from_settings() -> None:
    settings = ModeSettingsOut(quote_refresh_minutes=15)
    assert quote_cache_ttl_seconds(settings) == 900


def test_quote_cache_ttl_max_minutes() -> None:
    settings = ModeSettingsOut(quote_refresh_minutes=120)
    assert quote_cache_ttl_seconds(settings) == 120 * 60


@pytest.mark.asyncio
async def test_get_or_set_skips_empty_failure_cache() -> None:
    init_db()
    key = "test:valuation:empty_fail"

    async def fetch_fail() -> dict[str, object]:
        return {
            "pe_ttm": None,
            "pb": None,
            "source": "none",
            "partial": True,
            "gaps": ["估值数据不可用"],
        }

    result = await get_or_set_cached_dict(key, 3600, fetch_fail)
    assert result["partial"] is True
    assert get_sqlite_cached(key) is None


@pytest.mark.asyncio
async def test_get_or_set_respects_should_cache() -> None:
    init_db()
    key = "test:valuation:should_cache"

    async def fetch_ok() -> dict[str, object]:
        return {
            "pe_ttm": 18.0,
            "pb": 5.5,
            "source": "akshare_value_em",
            "partial": False,
            "gaps": [],
        }

    result = await get_or_set_cached_dict(
        key, 3600, fetch_ok, should_cache=lambda p: p.get("pe_ttm") is not None
    )
    assert result["pe_ttm"] == 18.0
    cached = get_sqlite_cached(key)
    assert cached is not None
    assert cached["pe_ttm"] == 18.0
