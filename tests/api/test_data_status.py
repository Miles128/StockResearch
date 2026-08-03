"""Data source status API tests."""

from fastapi.testclient import TestClient

from stockresearch.data.registry import (
    record_overview_fetch,
    record_quote_fetch,
    reset_snapshots_for_tests,
)


def test_data_status_returns_snapshots(client: TestClient) -> None:
    reset_snapshots_for_tests()
    record_quote_fetch(requested=2, sina_count=1, akshare_count=1, message="部分降级")
    record_overview_fetch(source="sina", degraded=False)

    resp = client.get("/api/v1/market/data-status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["quotes"]["primary"] == "sina"
    assert body["quotes"]["fallback_count"] == 1
    assert body["quotes"]["degraded"] is True
    assert body["overview"]["primary"] == "sina"
    assert body["details"]
    quote_detail = next(item for item in body["details"] if item["domain"] == "quotes")
    assert quote_detail["label"] == "行情报价"
    assert quote_detail["layer"] == "L1"
    assert quote_detail["source"] == "sina + akshare"
    assert quote_detail["status"] == "degraded"
    assert quote_detail["degraded_reason"] == "部分降级"
