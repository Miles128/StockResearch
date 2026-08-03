"""GET /market/overlays route tests (Phase 9b)."""

from unittest.mock import AsyncMock, patch

from stockresearch.core.schemas import ChartOverlay, ChartOverlayPoint, ChartOverlaySet


def _overlay_set() -> ChartOverlaySet:
    return ChartOverlaySet(
        symbol="600519",
        generatedAt="2026-08-04T00:00:00+00:00",
        overlays=[
            ChartOverlay(
                id="trend-support-5-79",
                kind="trend",
                a=ChartOverlayPoint(time="2026-04-01", price=100.0),
                b=ChartOverlayPoint(time="2026-08-01", price=137.0),
                side="support",
                strength=1.0,
                touches=4,
                source="ai",
                rationale="支撑线示例，不构成交易建议。",
            )
        ],
    )


def test_market_overlays_returns_set(client, db_session) -> None:
    with patch(
        "stockresearch.api.routes.market.compute_chart_overlays",
        new=AsyncMock(return_value=_overlay_set()),
    ):
        resp = client.get("/api/v1/market/overlays?symbol=600519")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "600519"
    assert body["overlays"][0]["source"] == "ai"
    assert body["overlays"][0]["side"] == "support"


def test_market_overlays_rejects_invalid_symbol(client, db_session) -> None:
    resp = client.get("/api/v1/market/overlays?symbol=12345")
    assert resp.status_code == 422


def test_market_overlays_provider_failure_503(client, db_session) -> None:
    with patch(
        "stockresearch.api.routes.market.compute_chart_overlays",
        new=AsyncMock(side_effect=RuntimeError("provider down")),
    ):
        resp = client.get("/api/v1/market/overlays?symbol=600519")
    assert resp.status_code == 503
