"""Sina batch quote tests."""

import pytest

from stockresearch.core.config import Settings
from stockresearch.data.providers import market as market_mod
from stockresearch.data.providers.market import QuoteProvider


@pytest.fixture
def live_market_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        market_mod,
        "get_settings",
        lambda: Settings(use_mock_market_data=False),
    )


@pytest.mark.asyncio
async def test_batch_quotes_use_sina_only(
    monkeypatch: pytest.MonkeyPatch,
    live_market_settings: None,
) -> None:
    def fake_sina(symbols: list[str]) -> dict[str, dict[str, float | str]]:
        from datetime import UTC, datetime

        return {
            sym: {
                "symbol": sym,
                "name": f"N{sym}",
                "price": 10.0,
                "change_pct": 1.0,
                "high": 11.0,
                "low": 9.0,
                "volume": 100.0,
                "updated_at": datetime.now(UTC),
            }
            for sym in symbols
        }

    monkeypatch.setattr(market_mod, "fetch_sina_quotes", fake_sina)

    quotes = await QuoteProvider().get_quotes(["600519", "300750", "600519"])
    assert set(quotes) == {"600519", "300750"}
    assert quotes["600519"].price == 10.0


@pytest.mark.asyncio
async def test_quotes_fallback_to_akshare_when_sina_fails(
    monkeypatch: pytest.MonkeyPatch,
    live_market_settings: None,
) -> None:
    def sina_fail(_symbols: list[str]) -> dict[str, dict[str, float | str]]:
        raise RuntimeError("sina down")

    def fake_ak(symbols: list[str]) -> dict[str, dict[str, float | str]]:
        from datetime import UTC, datetime

        return {
            sym: {
                "symbol": sym,
                "name": f"Ak{sym}",
                "price": 99.0,
                "change_pct": 0.5,
                "high": 100.0,
                "low": 98.0,
                "volume": 50.0,
                "updated_at": datetime.now(UTC),
            }
            for sym in symbols
        }

    monkeypatch.setattr(market_mod, "fetch_sina_quotes", sina_fail)
    monkeypatch.setattr(market_mod, "fetch_akshare_hist_quotes", fake_ak)

    quotes = await QuoteProvider().get_quotes(["600519"])
    assert quotes["600519"].price == 99.0
    assert quotes["600519"].name == "Ak600519"
