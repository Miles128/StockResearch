"""SQLite-backed cache for provider payloads — survives process restarts."""

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from stockresearch.db.session import SessionLocal


def get_sqlite_cached(key: str) -> dict[str, object] | None:
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT payload, expires_at FROM provider_cache " "WHERE cache_key = :key"),
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
