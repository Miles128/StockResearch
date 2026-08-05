"""SQLite-backed cache for provider payloads — survives process restarts."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from stockresearch.db.session import SessionLocal


# JSON payloads hold arbitrary values; use Any rather than object so callers can
# index/convert cached entries without casts.
def get_sqlite_cached(key: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT payload, expires_at FROM provider_cache WHERE cache_key = :key"),
            {"key": key},
        ).first()
        if row is None:
            return None
        payload_raw, expires_at = row
        if expires_at is not None:
            expires = (
                expires_at
                if isinstance(expires_at, datetime)
                else datetime.fromisoformat(str(expires_at))
            )
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            if datetime.now(UTC) > expires:
                db.execute(text("DELETE FROM provider_cache WHERE cache_key = :key"), {"key": key})
                db.commit()
                return None
        parsed = json.loads(str(payload_raw))
        return parsed if isinstance(parsed, dict) else None


def set_sqlite_cached(key: str, value: dict[str, object], ttl_seconds: int) -> None:
    expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
    payload = json.dumps(value, ensure_ascii=False)
    with SessionLocal() as db:
        _upsert_cache(db, key, payload, expires_at)
        db.commit()


def evict_sqlite_prefixes(
    prefixes: tuple[str, ...] | list[str], contains: str | None = None
) -> int:
    """Delete provider_cache rows whose cache_key starts with any prefix.

    When ``contains`` is given, only keys containing that substring are
    deleted (used to scope eviction to one symbol). Returns deleted count.
    """
    if not prefixes:
        return 0
    conditions = " OR ".join(["cache_key LIKE :p" + str(i) for i in range(len(prefixes))])
    params: dict[str, object] = {f"p{i}": prefix + "%" for i, prefix in enumerate(prefixes)}
    sql = f"DELETE FROM provider_cache WHERE ({conditions})"  # noqa: S608
    if contains:
        sql += " AND cache_key LIKE :contains"
        params["contains"] = f"%{contains}%"
    with SessionLocal() as db:
        result = db.execute(text(sql), params)
        db.commit()
        return cast(CursorResult, result).rowcount or 0


def _upsert_cache(db: Session, key: str, payload: str, expires_at: datetime) -> None:
    db.execute(
        text(
            "INSERT INTO provider_cache (cache_key, payload, expires_at) "
            "VALUES (:key, :payload, :expires_at) "
            "ON CONFLICT(cache_key) DO UPDATE SET "
            "payload = excluded.payload, expires_at = excluded.expires_at"
        ),
        {"key": key, "payload": payload, "expires_at": expires_at.isoformat()},
    )
