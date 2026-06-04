"""Sector backfill API tests."""

from fastapi.testclient import TestClient

from stockresearch.db.models import Holding
from stockresearch.services.auth import get_or_create_mvp_user


def test_backfill_sectors_api(client: TestClient, db_session: object) -> None:
    user = get_or_create_mvp_user(db_session)
    db_session.add(
        Holding(
            user_id=user.id,
            symbol="600519",
            name="贵州茅台",
            cost_price=1800.0,
            quantity=100,
            sector="未知",
        )
    )
    db_session.commit()

    resp = client.post("/api/v1/portfolio/holdings/backfill-sectors")
    assert resp.status_code == 200
    body = resp.json()
    assert body["updated"] == 1
    assert "补全" in body["message"]

    listing = client.get("/api/v1/portfolio/holdings")
    sectors = [item["sector"] for item in listing.json()]
    assert "白酒" in sectors
