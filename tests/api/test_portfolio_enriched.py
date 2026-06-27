"""Enriched holdings with quotes and P&L."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from stockresearch.services import trading_calendar as cal_mod

_BUY = date(2026, 5, 25)


def test_holdings_enriched_includes_quote_and_pnl(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from stockresearch.data.providers.market_overview import BatchQuoteProvider

    async def fake_get_quotes(self, symbols: list[str]):
        from stockresearch.core.schemas import StockQuoteOut
        return [
            StockQuoteOut(symbol=sym, name="贵州茅台", price=1680.0, change_pct=-1.2, high=1700.0, low=1660.0, volume=5000.0, source="test")
            for sym in symbols
        ]

    monkeypatch.setattr(BatchQuoteProvider, "get_quotes", fake_get_quotes)
    monkeypatch.setattr(cal_mod, "_load_trading_days", lambda: frozenset({_BUY}))
    create = client.post(
        "/api/v1/portfolio/holdings",
        json={
            "query": "600519",
            "cost_price": 1600.0,
            "quantity": 100,
            "buy_date": _BUY.isoformat(),
        },
    )
    assert create.status_code == 200

    resp = client.get("/api/v1/portfolio/holdings/enriched")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) >= 1
    row = next(r for r in rows if r["symbol"] == "600519")
    assert row["quote_available"] is True
    assert row["price"] == 1680.0
    assert row["change_pct"] == -1.2
    assert row["price_label"] in ("现价", "收盘")
    assert row["profit_amount"] == 8000.0
    assert row["profit_pct"] == 5.0
    assert row["annualized_pct"] is not None
