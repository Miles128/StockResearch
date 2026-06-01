"""Authentication helpers."""

from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from invesbao.core.config import get_settings
from invesbao.core.exceptions import AuthenticationError, NotFoundError
from invesbao.db.models import User

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return str(jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM))


def decode_user_id(token: str) -> int:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            raise AuthenticationError("Invalid token")
        return int(sub)
    except (JWTError, ValueError) as exc:
        raise AuthenticationError("Invalid token") from exc


def authenticate_user(db: Session, username: str, password: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid username or password")
    return user


MVP_USERNAME = "mvp"


def get_or_create_mvp_user(db: Session) -> User:
    user = db.query(User).filter(User.username == MVP_USERNAME).first()
    if user is not None:
        return user
    user = User(username=MVP_USERNAME, password_hash=hash_password("mvp-local-only"))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_id(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise NotFoundError(f"User {user_id} not found")
    return user
