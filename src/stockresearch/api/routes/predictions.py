"""预测日记（Phase 12a）路由 — 预测记录列表 / 准确率统计 / 单条详情。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from stockresearch.api.deps import get_current_user
from stockresearch.core.schemas import PredictionOut, PredictionStatsOut
from stockresearch.db.models import Prediction, User
from stockresearch.db.session import get_db
from stockresearch.services.prediction_journal import prediction_stats

router = APIRouter(prefix="/predictions", tags=["predictions"])


def _to_out(p: Prediction) -> PredictionOut:
    return PredictionOut(
        id=p.id,
        symbol=p.symbol,
        name=p.name,
        direction=p.direction,  # type: ignore[arg-type]
        confidence=p.confidence,  # type: ignore[arg-type]
        horizon_days=p.horizon_days,
        claim=p.claim,
        report_id=p.report_id,
        created_at=p.created_at,
        due_at=p.due_at,
        status=p.status,  # type: ignore[arg-type]
        outcome=p.outcome,  # type: ignore[arg-type]
        actual_return_pct=float(p.actual_return_pct) if p.actual_return_pct is not None else None,
        scored_at=p.scored_at,
    )


@router.get("", response_model=list[PredictionOut])
def list_predictions(
    status: str | None = Query(default=None, pattern="^(pending|scored|skipped)$"),
    direction: str | None = Query(default=None, pattern="^(bullish|bearish|neutral)$"),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PredictionOut]:
    query = db.query(Prediction).filter(Prediction.user_id == user.id)
    if status:
        query = query.filter(Prediction.status == status)
    if direction:
        query = query.filter(Prediction.direction == direction)
    rows = query.order_by(Prediction.created_at.desc()).limit(limit).all()
    return [_to_out(r) for r in rows]


@router.get("/stats", response_model=PredictionStatsOut)
def get_prediction_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PredictionStatsOut:
    return PredictionStatsOut.model_validate(prediction_stats(db, user.id))


@router.get("/{prediction_id}", response_model=PredictionOut)
def get_prediction(
    prediction_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PredictionOut:
    row = (
        db.query(Prediction)
        .filter(Prediction.id == prediction_id, Prediction.user_id == user.id)
        .first()
    )
    if row is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Prediction not found")
    return _to_out(row)
