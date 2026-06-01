"""Portfolio API performance tests."""

import time

from fastapi.testclient import TestClient


def test_delete_holding(client: TestClient) -> None:
    create = client.post(
        "/api/v1/portfolio/holdings",
        json={"query": "600519", "cost_price": 1800.0, "quantity": 1},
    )
    assert create.status_code == 200
    holding_id = create.json()["id"]

    delete = client.delete(f"/api/v1/portfolio/holdings/{holding_id}")
    assert delete.status_code == 200

    listing = client.get("/api/v1/portfolio/holdings")
    assert all(item["id"] != holding_id for item in listing.json())


def test_add_holding_builtin_symbol_is_fast(client: TestClient) -> None:
    started = time.monotonic()
    resp = client.post(
        "/api/v1/portfolio/holdings",
        json={"query": "600519", "cost_price": 1800.0, "quantity": 10},
    )
    elapsed = time.monotonic() - started
    assert resp.status_code == 200
    assert resp.json()["symbol"] == "600519"
    assert elapsed < 2.0, f"add holding took {elapsed:.1f}s, expected instant for built-in symbol"
