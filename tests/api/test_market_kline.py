"""Market kline chart API tests."""

from fastapi.testclient import TestClient


def test_kline_chart(client: TestClient) -> None:
    resp = client.get("/api/v1/market/kline?symbol=600519&days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "600519"
    assert len(data["bars"]) >= 10
    bar = data["bars"][0]
    assert "date" in bar and "close" in bar
    ind = data["indicators"]
    assert len(ind["rsi"]) == len(data["bars"])
    assert len(ind["macd"]) == len(data["bars"])
