"""风控告警持久化（从 API 路由层下沉，脱离 HTTP 可复用/可测）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from stockresearch.core.schemas import RiskCheckupOut
from stockresearch.db.models import RiskAlertRecord


def persist_alerts(db: Session, user_id: int, result: RiskCheckupOut) -> None:
    for alert in result.alerts:
        db.add(
            RiskAlertRecord(
                user_id=user_id,
                rule_id=alert.rule_id,
                severity=alert.severity,
                symbol=alert.symbol,
                message=alert.message,
            )
        )
    db.commit()
