"""Tests for provider cache TTL policy."""

from stockresearch.core.schemas import ModeSettingsOut
from stockresearch.services.provider_cache_policy import (
    DEFAULT_QUOTE_CACHE_TTL_SECONDS,
    quote_cache_ttl_seconds,
)


def test_quote_cache_ttl_default() -> None:
    assert quote_cache_ttl_seconds(None) == DEFAULT_QUOTE_CACHE_TTL_SECONDS


def test_quote_cache_ttl_from_settings() -> None:
    settings = ModeSettingsOut(quote_refresh_minutes=15)
    assert quote_cache_ttl_seconds(settings) == 900


def test_quote_cache_ttl_max_minutes() -> None:
    settings = ModeSettingsOut(quote_refresh_minutes=120)
    assert quote_cache_ttl_seconds(settings) == 120 * 60
