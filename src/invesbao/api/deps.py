"""FastAPI dependencies."""

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from invesbao.core.exceptions import AuthenticationError, InvesBaoError, NotFoundError, ValidationError
from invesbao.db.models import User
from invesbao.db.session import get_db
from invesbao.services.auth import get_or_create_mvp_user


def get_current_user(db: Session = Depends(get_db)) -> User:
    """MVP: single local user, no login required."""
    return get_or_create_mvp_user(db)


def handle_invesbao_error(exc: InvesBaoError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, AuthenticationError):
        return HTTPException(status_code=401, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))
