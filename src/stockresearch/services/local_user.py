"""Local single-user helpers (no login)."""

from sqlalchemy.orm import Session

from stockresearch.db.models import User

MVP_USERNAME = "mvp"


def get_or_create_mvp_user(db: Session) -> User:
    user = db.query(User).filter(User.username == MVP_USERNAME).first()
    if user is not None:
        return user
    user = User(username=MVP_USERNAME, password_hash="")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
