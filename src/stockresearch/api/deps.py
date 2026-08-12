"""FastAPI dependencies."""

from fastapi import Depends
from sqlalchemy.orm import Session

from stockresearch.db.models import User
from stockresearch.db.session import get_db
from stockresearch.services.local_user import get_or_create_mvp_user


def get_current_user(db: Session = Depends(get_db)) -> User:
    """Single local user; no login."""
    return get_or_create_mvp_user(db)
