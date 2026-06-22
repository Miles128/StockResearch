"""Daily Action Center routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from stockresearch.api.deps import get_current_user
from stockresearch.core.schemas import DailyActionCenterOut
from stockresearch.db.models import User
from stockresearch.db.session import get_db
from stockresearch.services.action_center import generate_daily_actions

router = APIRouter(prefix="/action-center", tags=["action-center"])


@router.get("/daily", response_model=DailyActionCenterOut)
async def daily_action_center(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyActionCenterOut:
    return await generate_daily_actions(db, user.id)
