"""Database session management."""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from stockresearch.core.config import get_settings
from stockresearch.db.models import Base

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_database_url(url: str) -> str:
    if url.startswith("sqlite:///./"):
        db_name = url.removeprefix("sqlite:///./")
        return f"sqlite:///{(_PROJECT_ROOT / db_name).as_posix()}"
    return url


_settings = get_settings()
_db_url = _resolve_database_url(_settings.database_url)
_connect_args = {"check_same_thread": False} if _db_url.startswith("sqlite") else {}
engine = create_engine(_db_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
