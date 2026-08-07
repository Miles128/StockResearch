"""预测日记（Phase 12a）路由 — 预测记录列表 / 准确率统计 / 单条详情。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from stockresearch.api.deps import get_current_user
from stockresearch.api.llm_deps import llm_from_headers
from stockresearch.core.schemas import (
    DimensionAttributionOut,
    PredictionOut,
    PredictionReviewOut,
    PredictionStatsOut,
    ThesisVerificationOut,
)
from stockresearch.db.models import Prediction, ThesisVerification, User
from stockresearch.db.session import get_db
from stockresearch.services.prediction_journal import (
    dimension_attribution,
    generate_prediction_review,
    prediction_stats,
)
from stockresearch.utils.llm import LLMClient

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


@router.get("/thesis", response_model=list[ThesisVerificationOut])
def list_thesis_verifications(
    report_id: int | None = Query(default=None),
    status: str | None = Query(default=None, pattern="^(pending|verified)$"),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ThesisVerificationOut]:
    query = db.query(ThesisVerification).filter(ThesisVerification.user_id == user.id)
    if report_id is not None:
        query = query.filter(ThesisVerification.report_id == report_id)
    if status:
        query = query.filter(ThesisVerification.status == status)
    rows = query.order_by(ThesisVerification.created_at.desc()).limit(limit).all()
    return [ThesisVerificationOut.model_validate(r) for r in rows]


@router.get("/attribution", response_model=DimensionAttributionOut)
def get_attribution(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DimensionAttributionOut:
    return DimensionAttributionOut.model_validate(dimension_attribution(db, user.id))


@router.post("/{prediction_id}/review", response_model=PredictionReviewOut)
async def review_prediction(
    prediction_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(llm_from_headers),
) -> PredictionReviewOut:
    p = await generate_prediction_review(db, user.id, prediction_id, llm)
    if p is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Prediction not found")
    if p.status != "scored":
        raise HTTPException(status_code=409, detail="Prediction not scored yet")
    return PredictionReviewOut(id=p.id, review_text=p.review_text or "")


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
