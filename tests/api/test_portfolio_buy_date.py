"""Portfolio buy_date validation on create."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from stockresearch.services import trading_calendar as cal_mod


def test_create_holding_rejects_non_trading_buy_date(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cal_mod,
        "_load_trading_days",
        lambda: frozenset({date(2026, 5, 25)}),
    )
    resp = client.post(
        "/api/v1/portfolio/holdings",
        json={
            "symbol": "600519",
            "name": "贵州茅台",
            "cost_price": 100.0,
            "lots": 1,
            "buy_date": "2026-05-24",
        },
    )
    assert resp.status_code == 422
    assert "交易日" in resp.json()["detail"]
