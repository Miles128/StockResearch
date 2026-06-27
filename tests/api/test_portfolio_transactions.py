"""Batch buy/sell holding transactions."""

from fastapi.testclient import TestClient


def _buy(client: TestClient, *, symbol: str = "600519", name: str = "贵州茅台", lots: int = 1) -> None:
    resp = client.post(
        "/api/v1/portfolio/holdings/transactions",
        json={
            "transactions": [
                {
                    "side": "buy",
                    "symbol": symbol,
                    "name": name,
                    "cost_price": 1800.0,
                    "lots": lots,
                    "trade_date": "2024-01-02",
                }
            ]
        },
    )
    assert resp.status_code == 200, resp.text


def test_batch_buy_and_sell(client: TestClient) -> None:
    _buy(client, lots=2)
    listing = client.get("/api/v1/portfolio/holdings")
    assert listing.json()[0]["quantity"] == 200

    sell = client.post(
        "/api/v1/portfolio/holdings/transactions",
        json={
            "transactions": [
                {"side": "sell", "symbol": "600519", "name": "贵州茅台", "lots": 1},
            ]
        },
    )
    assert sell.status_code == 200, sell.text
    assert sell.json()["holdings"][0]["quantity"] == 100


def test_sell_exceeds_holdings_returns_error(client: TestClient) -> None:
    _buy(client, lots=1)
    resp = client.post(
        "/api/v1/portfolio/holdings/transactions",
        json={
            "transactions": [
                {"side": "sell", "symbol": "600519", "name": "贵州茅台", "lots": 2},
            ]
        },
    )
    assert resp.status_code == 422
    assert "超出持仓" in resp.json()["detail"]
