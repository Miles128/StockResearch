"""FastAPI dependencies."""

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from stockresearch.core.exceptions import NotFoundError, StockResearchError, ValidationError
from stockresearch.db.models import User
from stockresearch.db.session import get_db
from stockresearch.services.local_user import get_or_create_mvp_user


def get_current_user(db: Session = Depends(get_db)) -> User:
    """Single local user; no login."""
    return get_or_create_mvp_user(db)


def handle_stockresearch_error(exc: StockResearchError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))
