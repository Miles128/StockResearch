"""Tests for database session management."""

from sqlalchemy import inspect

from stockresearch.db.models import Base
from stockresearch.db.session import SessionLocal, init_db


def test_init_db_creates_tables() -> None:
    init_db()
    inspector = inspect(SessionLocal.kw["bind"])
    table_names = inspector.get_table_names()
    assert "users" in table_names
    assert "holdings" in table_names
    assert "watchlist" in table_names
    assert "conversations" in table_names
    assert "user_preferences" in table_names
    assert "provider_cache" in table_names
    assert "schema_migrations" in table_names


def test_session_local_works() -> None:
    init_db()
    session = SessionLocal()
    try:
        result = session.execute(Base.metadata.tables["users"].select())
        rows = result.fetchall()
        assert isinstance(rows, list)
    finally:
        session.close()
