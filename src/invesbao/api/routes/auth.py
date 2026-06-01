"""Authentication routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from invesbao.api.deps import get_current_user, handle_invesbao_error
from invesbao.core.exceptions import AuthenticationError
from invesbao.core.schemas import TokenResponse, UserCreate, UserLogin, UserOut
from invesbao.db.models import User
from invesbao.db.session import get_db
from invesbao.services.auth import authenticate_user, create_access_token, hash_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(username=payload.username, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        user = authenticate_user(db, payload.username, payload.password)
    except AuthenticationError as exc:
        raise handle_invesbao_error(exc) from exc
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
