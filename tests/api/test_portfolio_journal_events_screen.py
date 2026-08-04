"""Decision journal (trade→report link), event calendar, factor screener."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from stockresearch.core.schemas import NumericFactorOut
from stockresearch.db.models import ResearchReport


def _buy(client: TestClient, symbol: str = "600519", name: str = "贵州茅台") -> None:
    resp = client.post(
        "/api/v1/portfolio/holdings/transactions",
        json={
            "transactions": [
                {
                    "side": "buy",
                    "symbol": symbol,
                    "name": name,
                    "cost_price": 1800.0,
                    "lots": 1,
                }
            ]
        },
    )
    assert resp.status_code == 200, resp.text


def test_trade_linked_to_latest_report(client: TestClient, db_session) -> None:
    report = ResearchReport(
        user_id=None,
        symbol="600519",
        name="贵州茅台",
        report_json={"bias": "bullish", "composite_score": 7.2},
    )
    db_session.add(report)
    db_session.commit()

    _buy(client)
    rows = client.get("/api/v1/portfolio/trades").json()
    assert len(rows) == 1
    assert rows[0]["report_id"] == report.id
    assert rows[0]["report_bias"] == "bullish"
    assert rows[0]["report_date"]


def test_trade_without_report_has_null_link(client: TestClient) -> None:
    _buy(client)
    rows = client.get("/api/v1/portfolio/trades").json()
    assert rows[0]["report_id"] is None
    assert rows[0]["report_bias"] is None


def test_events_calendar(client: TestClient, monkeypatch) -> None:
    from stockresearch.services import events_calendar

    earnings_date = date.today() + timedelta(days=5)
    lockup_date = date.today() + timedelta(days=10)

    async def _fake_earnings(period):
        return {"600519": earnings_date}

    async def _fake_lockups(symbol):
        if symbol == "600519":
            return [(lockup_date, "解禁 1.20 亿股")]
        return []

    monkeypatch.setattr(events_calendar, "_fetch_earnings_schedule", _fake_earnings)
    monkeypatch.setattr(events_calendar, "_fetch_lockups", _fake_lockups)
    _buy(client)

    resp = client.get("/api/v1/portfolio/events", params={"days": 45})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    kinds = {(e["kind"], e["event_date"]) for e in body["events"]}
    assert ("earnings", earnings_date.isoformat()) in kinds
    assert ("lockup", lockup_date.isoformat()) in kinds
    assert all(e["scope"] == "holding" for e in body["events"])


def test_events_empty_universe(client: TestClient) -> None:
    resp = client.get("/api/v1/portfolio/events")
    assert resp.status_code == 200
    body = resp.json()
    assert body["events"] == []
    assert body["message"]


def _fake_factor(key: str, value: float | None) -> NumericFactorOut:
    return NumericFactorOut(key=key, label=key, value=value, unit="%")


def test_screener_filters_by_conditions(client: TestClient, monkeypatch) -> None:
    from stockresearch.services import screener

    _buy(client, symbol="600519")
    _buy(client, symbol="000858", name="五粮液")

    async def _fake_factors(symbol, *, factor_keys=None):
        if symbol == "600519":
            factors = [_fake_factor("momentum_20d", 5.0), _fake_factor("pe_percentile", 20.0)]
        else:
            factors = [_fake_factor("momentum_20d", -3.0), _fake_factor("pe_percentile", 80.0)]
        return factors, None

    monkeypatch.setattr(screener, "compute_numeric_factors", _fake_factors)

    resp = client.post(
        "/api/v1/portfolio/screen",
        json={
            "universe": "holdings",
            "conditions": [
                {"key": "momentum_20d", "op": ">", "value": 0},
                {"key": "pe_percentile", "op": "<=", "value": 30},
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scanned"] == 2
    assert body["skipped"] == 0
    assert [h["symbol"] for h in body["hits"]] == ["600519"]
    assert body["hits"][0]["factors"]["momentum_20d"] == 5.0


def test_screener_skips_missing_factors(client: TestClient, monkeypatch) -> None:
    from stockresearch.services import screener

    _buy(client)

    async def _fake_factors(symbol, *, factor_keys=None):
        return [_fake_factor("momentum_20d", None)], None

    monkeypatch.setattr(screener, "compute_numeric_factors", _fake_factors)

    resp = client.post(
        "/api/v1/portfolio/screen",
        json={
            "universe": "holdings",
            "conditions": [{"key": "momentum_20d", "op": ">", "value": 0}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["hits"] == []
    assert body["skipped"] == 1
