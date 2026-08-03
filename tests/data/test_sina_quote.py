"""Sina batch quote tests."""

import pytest

from stockresearch.data.providers.market import MarketRuleProvider, QuoteProvider
from stockresearch.data.providers.market import quotes as quotes_mod
from stockresearch.data.providers.market import rules as rules_mod
from stockresearch.data.providers.sina_quote import QuoteRow


@pytest.fixture(autouse=True)
def noop_sqlite_quote_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(quotes_mod, "get_sqlite_cached", lambda _key: None)
    monkeypatch.setattr(quotes_mod, "set_sqlite_cached", lambda *_args, **_kwargs: None)


@pytest.mark.asyncio
async def test_batch_quotes_use_sina_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_sina(symbols: list[str]) -> dict[str, QuoteRow]:
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

    monkeypatch.setattr(quotes_mod, "fetch_sina_quotes", fake_sina)

    quotes = await QuoteProvider().get_quotes(["600519", "300750", "600519"], force_refresh=True)
    assert set(quotes) == {"600519", "300750"}
    assert quotes["600519"].price == 10.0


@pytest.mark.asyncio
async def test_quotes_fallback_to_akshare_when_sina_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def sina_fail(_symbols: list[str]) -> dict[str, QuoteRow]:
        raise RuntimeError("sina down")

    def fake_ak(symbols: list[str]) -> dict[str, QuoteRow]:
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

    monkeypatch.setattr(quotes_mod, "fetch_sina_quotes", sina_fail)
    monkeypatch.setattr(quotes_mod, "fetch_efinance_quotes", lambda _s: {})
    monkeypatch.setattr(quotes_mod, "fetch_akshare_hist_quotes", fake_ak)

    quotes = await QuoteProvider().get_quotes(["600519"], force_refresh=True)
    assert quotes["600519"].price == 99.0
    assert quotes["600519"].name == "Ak600519"


@pytest.mark.asyncio
async def test_quotes_sync_fill_missing_on_partial_sina(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime

    ak_called = False

    def fake_sina(symbols: list[str]) -> dict[str, QuoteRow]:
        return {
            "600519": {
                "symbol": "600519",
                "name": "贵州茅台",
                "price": 10.0,
                "change_pct": 1.0,
                "high": 11.0,
                "low": 9.0,
                "volume": 100.0,
                "updated_at": datetime.now(UTC),
            }
        }

    def fake_ef(_symbols: list[str]) -> dict[str, QuoteRow]:
        return {}

    def fake_ak(_symbols: list[str]) -> dict[str, QuoteRow]:
        nonlocal ak_called
        ak_called = True
        return {
            "300750": {
                "symbol": "300750",
                "name": "宁德时代",
                "price": 200.0,
                "change_pct": -1.0,
                "high": 205.0,
                "low": 198.0,
                "volume": 1000.0,
                "updated_at": datetime.now(UTC),
            }
        }

    monkeypatch.setattr(quotes_mod, "fetch_sina_quotes", fake_sina)
    monkeypatch.setattr(quotes_mod, "fetch_efinance_quotes", fake_ef)
    monkeypatch.setattr(quotes_mod, "fetch_akshare_hist_quotes", fake_ak)

    quotes = await QuoteProvider().get_quotes(["600519", "300750"], force_refresh=True)
    assert quotes["600519"].price == 10.0
    assert quotes["300750"].price == 200.0
    assert ak_called is True


@pytest.mark.asyncio
async def test_trading_rules_detect_limit_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_sina(_symbols: list[str]) -> dict[str, QuoteRow]:
        from datetime import UTC, datetime

        return {
            "600519": {
                "symbol": "600519",
                "name": "贵州茅台",
                "price": 110.0,
                "prev_close": 100.0,
                "open": 105.0,
                "change_pct": 10.0,
                "high": 110.0,
                "low": 100.0,
                "volume": 100.0,
                "updated_at": datetime.now(UTC),
            }
        }

    monkeypatch.setattr(rules_mod, "fetch_sina_quotes", fake_sina)

    rules = await MarketRuleProvider().get_trading_rules("600519")
    assert rules["verified"] is True
    assert rules["status"] == "limit_up"
    assert rules["is_limit_up"] is True
    assert rules["limit_pct"] == 10.0


@pytest.mark.asyncio
async def test_trading_rules_detect_st_and_suspended(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_sina(_symbols: list[str]) -> dict[str, QuoteRow]:
        from datetime import UTC, datetime

        return {
            "600000": {
                "symbol": "600000",
                "name": "*ST测试",
                "price": 0.0,
                "prev_close": 10.0,
                "open": 0.0,
                "change_pct": 0.0,
                "high": 0.0,
                "low": 0.0,
                "volume": 0.0,
                "updated_at": datetime.now(UTC),
            }
        }

    monkeypatch.setattr(rules_mod, "fetch_sina_quotes", fake_sina)

    rules = await MarketRuleProvider().get_trading_rules("600000")
    assert rules["is_st"] is True
    assert rules["is_suspended"] is True
    assert rules["status"] == "suspended"
    assert rules["limit_pct"] == 5.0


def test_trading_rule_limit_pct_by_board() -> None:
    provider = MarketRuleProvider()
    assert provider._limit_pct("300750", "宁德时代") == 20.0
    assert provider._limit_pct("688001", "华兴源创") == 20.0
    assert provider._limit_pct("830000", "北交所样本") == 30.0
    assert provider._limit_pct("600000", "浦发银行") == 10.0
