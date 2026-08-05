"""Price alert settings and in-app notifications."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from stockresearch.api.deps import get_current_user
from stockresearch.core.schemas import (
    PriceAlertNotificationOut,
    PriceAlertSettingsOut,
    PriceAlertSettingsUpdate,
)
from stockresearch.db.models import PriceAlertNotification, User
from stockresearch.db.session import get_db
from stockresearch.services.price_alerts import get_or_create_settings

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/settings", response_model=PriceAlertSettingsOut)
def get_alert_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PriceAlertSettingsOut:
    row = get_or_create_settings(db, user.id)
    return PriceAlertSettingsOut(enabled=row.enabled, threshold_pct=float(row.threshold_pct))


@router.put("/settings", response_model=PriceAlertSettingsOut)
def update_alert_settings(
    payload: PriceAlertSettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PriceAlertSettingsOut:
    row = get_or_create_settings(db, user.id)
    if payload.enabled is not None:
        row.enabled = payload.enabled
    if payload.threshold_pct is not None:
        row.threshold_pct = payload.threshold_pct
    db.commit()
    db.refresh(row)
    return PriceAlertSettingsOut(enabled=row.enabled, threshold_pct=float(row.threshold_pct))


@router.get("/notifications", response_model=list[PriceAlertNotificationOut])
def list_notifications(
    unread_only: bool = False,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PriceAlertNotification]:
    q = db.query(PriceAlertNotification).filter(PriceAlertNotification.user_id == user.id)
    if unread_only:
        q = q.filter(PriceAlertNotification.read.is_(False))
    return q.order_by(PriceAlertNotification.created_at.desc()).limit(limit).all()


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    row = (
        db.query(PriceAlertNotification)
        .filter(
            PriceAlertNotification.id == notification_id,
            PriceAlertNotification.user_id == user.id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    row.read = True
    db.commit()
    return {"status": "ok"}


@router.post("/notifications/read-all")
def mark_all_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    updated = (
        db.query(PriceAlertNotification)
        .filter(
            PriceAlertNotification.user_id == user.id,
            PriceAlertNotification.read.is_(False),
        )
        .update({PriceAlertNotification.read: True})
    )
    db.commit()
    return {"updated": updated}


@router.post("/check")
async def trigger_alert_check(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str | int]:
    """Manual trigger for dev / immediate check."""
    from stockresearch.services.price_alerts import check_price_alerts_for_user

    created = await check_price_alerts_for_user(db, user.id)
    return {"created": created, "trading_date": date.today().isoformat()}
