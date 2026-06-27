"""SQLite provider cache tests."""

from stockresearch.db.session import init_db
from stockresearch.services.sqlite_cache import get_sqlite_cached, set_sqlite_cached


def test_sqlite_cache_roundtrip() -> None:
    init_db()
    key = "test:600519:northbound"
    assert get_sqlite_cached(key) is None
    set_sqlite_cached(key, {"hold_pct": 6.5, "source": "akshare_northbound"}, ttl_seconds=3600)
    cached = get_sqlite_cached(key)
    assert cached is not None
    assert cached["hold_pct"] == 6.5
