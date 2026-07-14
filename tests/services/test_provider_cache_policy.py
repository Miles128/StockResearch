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
async def test_get_or_set_skips_empty_peers() -> None:
    init_db()
    key = "test:peers:empty"

    async def fetch_empty() -> dict[str, object]:
        return {"peers": [], "source": "none"}

    result = await get_or_set_cached_dict(key, 3600, fetch_empty)
    assert result["peers"] == []
    assert get_sqlite_cached(key) is None


@pytest.mark.asyncio
async def test_get_or_set_skips_tushare_no_percentile() -> None:
    init_db()
    key = "test:valuation:tushare_partial"

    async def fetch_partial() -> dict[str, object]:
        return {
            "pe_ttm": 20.0,
            "pb": 3.0,
            "pe_percentile": None,
            "source": "tushare_daily_basic",
            "partial": True,
            "gaps": ["Tushare 仅提供当日估值，无历史分位"],
        }

    result = await get_or_set_cached_dict(key, 3600, fetch_partial)
    assert result["pe_ttm"] == 20.0
    assert get_sqlite_cached(key) is None


@pytest.mark.asyncio
async def test_get_or_set_skips_chips_empty_signal() -> None:
    init_db()
    key = "test:chips:empty"

    async def fetch_empty() -> dict[str, object]:
        return {
            "appearances": 0,
            "net_buy": 0.0,
            "signal": "暂无数据",
            "source": "akshare_lhb",
        }

    result = await get_or_set_cached_dict(key, 3600, fetch_empty)
    assert result["signal"] == "暂无数据"
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
