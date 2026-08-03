"""Database session management."""

from collections.abc import Callable, Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

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

if _db_url == "sqlite://":
    # 内存数据库（测试）：必须共享同一连接，否则每次连接都是新的空库。
    engine = create_engine(_db_url, connect_args=_connect_args, poolclass=StaticPool)
elif _db_url.startswith("sqlite"):
    # 本地文件 SQLite 单用户 MVP：避免 QueuePool 耗尽，每个请求独立连接。
    engine = create_engine(_db_url, connect_args=_connect_args, poolclass=NullPool)
else:
    engine = create_engine(
        _db_url,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
    )

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _column_exists(conn: Connection, table: str, column: str) -> bool:
    """检测列是否存在，避免用异常吞咽区分 schema 状态。"""
    inspector = inspect(conn)
    if table not in inspector.get_table_names():
        return False
    return column in {col["name"] for col in inspector.get_columns(table)}


def _migration_001_conversation_checkpoint(conn: Connection) -> None:
    if not _column_exists(conn, "conversations", "checkpoint"):
        conn.execute(text("ALTER TABLE conversations ADD COLUMN checkpoint JSON"))


def _migration_002_user_preferences(conn: Connection) -> None:
    conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS user_preferences ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "user_id INTEGER NOT NULL UNIQUE, "
            "mode_settings JSON NOT NULL, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "FOREIGN KEY(user_id) REFERENCES users(id)"
            ")"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_user_preferences_user_id "
            "ON user_preferences (user_id)"
        )
    )


def _migration_003_provider_cache(conn: Connection) -> None:
    conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS provider_cache ("
            "cache_key TEXT NOT NULL PRIMARY KEY, "
            "payload JSON NOT NULL, "
            "expires_at DATETIME, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_provider_cache_expires_at "
            "ON provider_cache (expires_at)"
        )
    )


_SQLITE_MIGRATIONS: list[tuple[int, str, Callable[[Connection], None]]] = [
    (1, "conversation_checkpoint", _migration_001_conversation_checkpoint),
    (2, "user_preferences", _migration_002_user_preferences),
    (3, "provider_cache", _migration_003_provider_cache),
]


def _migrate_sqlite_schema() -> None:
    """Apply versioned, idempotent migrations for the local SQLite database."""
    if not _db_url.startswith("sqlite"):
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version INTEGER PRIMARY KEY, "
                "name TEXT NOT NULL, "
                "applied_at DATETIME DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
        )
        applied = {
            int(row[0]) for row in conn.execute(text("SELECT version FROM schema_migrations"))
        }
        for version, name, migration in _SQLITE_MIGRATIONS:
            if version in applied:
                continue
            migration(conn)
            conn.execute(
                text("INSERT INTO schema_migrations(version, name) " "VALUES (:version, :name)"),
                {"version": version, "name": name},
            )


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite_schema()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
