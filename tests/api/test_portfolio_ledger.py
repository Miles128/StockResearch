"""Trade ledger (decision journal) + portfolio NAV curve vs benchmark."""

from datetime import date

from fastapi.testclient import TestClient

from stockresearch.data.providers.market import TechnicalDataProvider
from stockresearch.db.models import DailyBar


def _buy(
    client: TestClient,
    *,
    symbol: str = "600519",
    name: str = "贵州茅台",
    lots: int = 1,
    cost_price: float = 1800.0,
    trade_date: str = "2024-01-02",
    note: str | None = None,
) -> None:
    item: dict = {
        "side": "buy",
        "symbol": symbol,
        "name": name,
        "cost_price": cost_price,
        "lots": lots,
        "trade_date": trade_date,
    }
    if note:
        item["note"] = note
    resp = client.post("/api/v1/portfolio/holdings/transactions", json={"transactions": [item]})
    assert resp.status_code == 200, resp.text


def test_buy_sell_recorded_with_realized_pnl(client: TestClient) -> None:
    _buy(client, lots=2, cost_price=1800.0, note="看好提价逻辑")
    sell = client.post(
        "/api/v1/portfolio/holdings/transactions",
        json={
            "transactions": [
                {
                    "side": "sell",
                    "symbol": "600519",
                    "name": "贵州茅台",
                    "cost_price": 1900.0,
                    "lots": 1,
                    "note": "兑现部分收益",
                }
            ]
        },
    )
    assert sell.status_code == 200, sell.text

    trades = client.get("/api/v1/portfolio/trades")
    assert trades.status_code == 200
    rows = trades.json()
    assert len(rows) == 2
    sells = [t for t in rows if t["side"] == "sell"]
    buys = [t for t in rows if t["side"] == "buy"]
    assert len(sells) == 1 and len(buys) == 1
    # (1900 - 1800) * 100 股
    assert sells[0]["realized_pnl"] == 10000.0
    assert sells[0]["note"] == "兑现部分收益"
    assert buys[0]["note"] == "看好提价逻辑"
    assert buys[0]["quantity"] == 200


def test_sell_without_price_is_not_recorded(client: TestClient) -> None:
    _buy(client)
    sell = client.post(
        "/api/v1/portfolio/holdings/transactions",
        json={
            "transactions": [{"side": "sell", "symbol": "600519", "name": "贵州茅台", "lots": 1}]
        },
    )
    assert sell.status_code == 200, sell.text
    rows = client.get("/api/v1/portfolio/trades").json()
    assert [t["side"] for t in rows] == ["buy"]


def _seed_bars(db_session) -> None:
    closes = {"600519": [100.0, 102.0, 104.0, 106.0], "000300": [1000.0, 1005.0, 1002.0, 1010.0]}
    dates = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4), date(2024, 1, 5)]
    for symbol, series in closes.items():
        for d, close in zip(dates, series):
            db_session.add(
                DailyBar(
                    symbol=symbol,
                    trade_date=d,
                    open=close,
                    high=close,
                    low=close,
                    close=close,
                    volume=1000.0,
                    adj="qfq",
                )
            )
    db_session.commit()


def test_performance_curve_vs_benchmark(client: TestClient, db_session, monkeypatch) -> None:
    async def _fake_bars(self, symbol, days=90, *, before=None, prefer_qfq=False):
        assert symbol == "000300"
        return [
            {"date": "2024-01-02", "close": 1000.0},
            {"date": "2024-01-03", "close": 1005.0},
            {"date": "2024-01-04", "close": 1002.0},
            {"date": "2024-01-05", "close": 1010.0},
        ]

    monkeypatch.setattr(TechnicalDataProvider, "get_kline_bars", _fake_bars)
    _seed_bars(db_session)
    _buy(client, cost_price=100.0, trade_date="2024-01-02")

    resp = client.get("/api/v1/portfolio/performance", params={"days": 20})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["series"]) == 4
    assert body["series"][0]["portfolio_index"] == 100.0
    assert body["series"][0]["benchmark_index"] == 100.0
    # 100 股 × (106/100 - 1)
    assert body["portfolio_return_pct"] == 6.0
    assert body["benchmark_return_pct"] == 1.0
    assert body["trade_count"] == 1


def test_performance_partial_without_bars(client: TestClient, monkeypatch) -> None:
    async def _fake_bars(self, symbol, days=90, *, before=None, prefer_qfq=False):
        return [{"date": "2024-01-02", "close": 1000.0}]

    monkeypatch.setattr(TechnicalDataProvider, "get_kline_bars", _fake_bars)
    _buy(client)

    resp = client.get("/api/v1/portfolio/performance")
    assert resp.status_code == 200
    body = resp.json()
    assert body["partial"] is True
    assert body["series"] == []
    assert body["message"]
