"""Data source status API tests."""

from stockresearch.data.registry import record_overview_fetch, record_quote_fetch, reset_snapshots_for_tests


def test_data_status_returns_snapshots(client) -> None:
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
