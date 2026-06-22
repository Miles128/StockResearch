"""Database session management."""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
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


def _column_exists(conn, table: str, column: str) -> bool:
    """检测列是否存在，避免用异常吞咽区分 schema 状态。"""
    inspector = inspect(conn)
    if table not in inspector.get_table_names():
        return False
    return column in {col["name"] for col in inspector.get_columns(table)}


def _migrate_sqlite_columns() -> None:
    """增量列迁移。用 inspector 显式检测列存在性，避免静默吞咽 SQL 错误。"""
    if not _db_url.startswith("sqlite"):
        return
    migrations: list[tuple[str, str, str]] = [
        # (table, column, DDL)
        ("conversations", "checkpoint", "ALTER TABLE conversations ADD COLUMN checkpoint JSON"),
    ]
    with engine.begin() as conn:
        for table, column, ddl in migrations:
            if not _column_exists(conn, table, column):
                conn.execute(text(ddl))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite_columns()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
