"""Portfolio lookup API tests."""

from fastapi.testclient import TestClient


def test_lookup_stock_by_name(client: TestClient) -> None:
    resp = client.post("/api/v1/portfolio/holdings/lookup", json={"query": "贵州茅台"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "confirmed"
    assert data["symbol"] == "600519"


def test_confirm_holding_merges_same_symbol(client: TestClient) -> None:
    first = client.post(
        "/api/v1/portfolio/holdings/confirm",
        json={"symbol": "600519", "name": "贵州茅台", "cost_price": 1800.0, "lots": 1},
    )
    assert first.status_code == 200
    assert first.json()["quantity"] == 100

    second = client.post(
        "/api/v1/portfolio/holdings/confirm",
        json={"symbol": "600519", "name": "贵州茅台", "cost_price": 1900.0, "lots": 2},
    )
    assert second.status_code == 200
    assert second.json()["quantity"] == 300
    assert second.json()["id"] == first.json()["id"]

    listing = client.get("/api/v1/portfolio/holdings")
    assert len(listing.json()) == 1


def test_confirm_holding_with_lots(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/portfolio/holdings/confirm",
        json={
            "symbol": "600519",
            "name": "贵州茅台",
            "cost_price": 1800.0,
            "lots": 2,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["quantity"] == 200
