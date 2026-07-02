"""Data provider tests — exercise real fetch paths, not global mock market."""

import pytest

from stockresearch.core.config import get_settings


@pytest.fixture(autouse=True)
def _disable_mock_market_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USE_MOCK_MARKET_DATA", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
