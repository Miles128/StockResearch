"""Tests for database session management."""

from sqlalchemy import inspect, text

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


def test_migration_009_adds_holding_buy_date_to_existing_table() -> None:
    """回归：旧库（holdings 表缺 buy_date 列）迁移后补列，不再 500。"""
    init_db()
    with SessionLocal.kw["bind"].begin() as conn:
        conn.execute(text("ALTER TABLE holdings DROP COLUMN buy_date"))
        # 模拟旧库状态：该迁移尚未记录
        conn.execute(text("DELETE FROM schema_migrations WHERE version = 9"))
    init_db()  # 重新跑迁移 → 应补回 buy_date
    with SessionLocal.kw["bind"].begin() as conn:
        row = conn.execute(text("PRAGMA table_info(holdings)")).fetchall()
    assert any(r[1] == "buy_date" for r in row)


def test_session_local_works() -> None:
    init_db()
    session = SessionLocal()
    try:
        result = session.execute(Base.metadata.tables["users"].select())
        rows = result.fetchall()
        assert isinstance(rows, list)
    finally:
        session.close()
