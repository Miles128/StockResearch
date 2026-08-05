"""Risk checkup history (continuous tracking) API tests."""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from stockresearch.db.models import RiskAlertRecord, User
from stockresearch.services.local_user import get_or_create_mvp_user


def _add_alerts(
    db,
    user_id: int,
    *,
    days_ago: int,
    red: int = 0,
    warning: int = 0,
    yellow: int = 0,
    critical: int = 0,
) -> None:
    """按规则引擎实际值域（red/warning/yellow/critical）写入告警。"""
    base = datetime.now() - timedelta(days=days_ago)
    severity_map = [
        ("red", red),
        ("warning", warning),
        ("yellow", yellow),
        ("critical", critical),
    ]
    for severity, count in severity_map:
        for i in range(count):
            db.add(
                RiskAlertRecord(
                    user_id=user_id,
                    rule_id=f"rule-{severity}",
                    severity=severity,
                    symbol="600519",
                    message=f"测试告警 {severity}",
                    created_at=base + timedelta(minutes=i),
                )
            )
    db.commit()


def test_checkup_history_groups_by_day_desc(client: TestClient, db_session) -> None:
    user = get_or_create_mvp_user(db_session)
    # red+critical 归入 high，warning → medium，yellow → low
    _add_alerts(db_session, user.id, days_ago=0, red=1, warning=2)
    _add_alerts(db_session, user.id, days_ago=1, critical=1, yellow=1)

    resp = client.get("/api/v1/risk/checkups/history")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_checks"] == 2
    items = data["items"]
    assert len(items) == 2
    assert items[0]["alert_count"] == 3
    assert items[0]["high_count"] == 1
    assert items[0]["medium_count"] == 2
    assert items[0]["low_count"] == 0
    assert items[1]["alert_count"] == 2
    assert items[1]["high_count"] == 1  # critical → high
    assert items[1]["medium_count"] == 0
    assert items[1]["low_count"] == 1
    # 按时间倒序
    assert items[0]["checked_at"] >= items[1]["checked_at"]


def test_checkup_history_empty(client: TestClient, db_session) -> None:
    resp = client.get("/api/v1/risk/checkups/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_checks"] == 0
    assert data["items"] == []


def test_checkup_history_other_user_isolated(client: TestClient, db_session) -> None:
    get_or_create_mvp_user(db_session)
    other = User(username="other_risk_user", password_hash="")
    db_session.add(other)
    db_session.commit()
    _add_alerts(db_session, other.id, days_ago=0, red=3)

    resp = client.get("/api/v1/risk/checkups/history")
    data = resp.json()
    assert data["total_checks"] == 0
