"""Phase 13b counterfactual teaching API — POST /portfolio/counterfactual."""

from fastapi.testclient import TestClient


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


def _fake_teaching_response(monkeypatch) -> None:
    from stockresearch.core.schemas import (
        CounterfactualSegmentOut,
        CounterfactualTeachingOut,
    )

    async def _fake_teaching(symbol: str, *, position_value: float | None = None):
        return CounterfactualTeachingOut(
            symbol=symbol,
            name=symbol,
            position_value=position_value,
            segments=[
                CounterfactualSegmentOut(
                    concept="drawdown",
                    title="回撤",
                    story=f"假设你买入 {position_value} 元……回撤教学",
                ),
                CounterfactualSegmentOut(
                    concept="volatility",
                    title="波动",
                    story="波动教学",
                ),
                CounterfactualSegmentOut(
                    concept="valuation",
                    title="估值",
                    story="估值教学",
                ),
            ],
            bars_adjust="qfq",
            bars_source="warehouse",
        )

    monkeypatch.setattr(
        "stockresearch.services.counterfactual_teaching.compute_counterfactual_teaching",
        _fake_teaching,
    )


def test_counterfactual_binds_position_value_to_holding(client: TestClient, monkeypatch) -> None:
    _buy(client)
    _fake_teaching_response(monkeypatch)
    resp = client.post("/api/v1/portfolio/counterfactual", json={"symbols": ["600519"]})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["symbol"] == "600519"
    assert item["position_value"] == 1800.0 * 100  # 1 手 = 100 股
    assert {seg["concept"] for seg in item["segments"]} == {
        "drawdown",
        "volatility",
        "valuation",
    }
    assert "180000.0 元" in item["segments"][0]["story"]


def test_counterfactual_non_holding_uses_demo_amount(client: TestClient, monkeypatch) -> None:
    _fake_teaching_response(monkeypatch)
    resp = client.post("/api/v1/portfolio/counterfactual", json={"symbols": ["000858"]})
    assert resp.status_code == 200, resp.text
    assert resp.json()["items"][0]["position_value"] is None


def test_counterfactual_skips_invalid_symbols(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/portfolio/counterfactual",
        json={"symbols": ["abc", "600519", "1234567", "SH600519"]},
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["items"]) == 1
    assert resp.json()["items"][0]["symbol"] == "600519"
