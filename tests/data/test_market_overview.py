"""Market overview provider tests."""

import time
from datetime import UTC, datetime

import pytest

from invesbao.core.config import Settings
from invesbao.core.schemas import IndexQuoteOut, MarketOverviewOut
from invesbao.data.providers import market_overview as mod
from invesbao.data.providers.market_overview import MarketOverviewProvider
from invesbao.data.providers.sina_index import SinaIndexQuote


@pytest.fixture
def live_market_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mod,
        "get_settings",
        lambda: Settings(use_mock_market_data=False),
    )


@pytest.mark.asyncio
async def test_overview_uses_sina_first(
    monkeypatch: pytest.MonkeyPatch,
    live_market_settings: None,
) -> None:
    monkeypatch.setattr(
        mod,
        "fetch_sina_indices",
        lambda: [
            SinaIndexQuote(name="上证指数", symbol="000001", price=3200.0, change_pct=0.5),
        ],
    )

    async def slow_akshare() -> MarketOverviewOut:
        raise AssertionError("AkShare should not run when Sina succeeds")

    provider = MarketOverviewProvider()
    monkeypatch.setattr(provider, "_fetch_akshare_indices_only", slow_akshare)

    started = time.monotonic()
    result = await provider.get_overview()
    elapsed = time.monotonic() - started

    assert elapsed < 0.5
    assert result.source == "sina"
    assert len(result.indices) == 1
    assert result.indices[0].price == 3200.0


@pytest.mark.asyncio
async def test_overview_akshare_fallback_times_out(
    monkeypatch: pytest.MonkeyPatch,
    live_market_settings: None,
) -> None:
    monkeypatch.setattr(mod, "fetch_sina_indices", lambda: (_ for _ in ()).throw(RuntimeError("sina down")))
    monkeypatch.setattr(mod, "_AKSHARE_FALLBACK_TIMEOUT_SEC", 0.2)

    def hang() -> MarketOverviewOut:
        time.sleep(2)
        return MarketOverviewOut(
            indices=[IndexQuoteOut(name="上证指数", symbol="000001", price=1.0, change_pct=0.0)],
            northbound_net_yi=None,
            advancers=None,
            decliners=None,
            source="akshare",
            data_status="live",
            message=None,
            updated_at=datetime.now(UTC),
        )

    provider = MarketOverviewProvider()
    monkeypatch.setattr(provider, "_fetch_akshare_indices_only", hang)

    started = time.monotonic()
    result = await provider.get_overview()
    elapsed = time.monotonic() - started

    assert elapsed < 1.0
    assert result.data_status == "unavailable"
