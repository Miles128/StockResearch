"""Rate limiting tests."""

from stockresearch.api.rate_limit import limiter
from stockresearch.db.models import User


def _clear_rate_limit_storage() -> None:
    storage = getattr(limiter, "_storage", None)
    if storage is not None and hasattr(storage, "storage"):
        storage.storage.clear()


def test_chat_rate_limit_returns_429(client, db_session) -> None:
    _clear_rate_limit_storage()
    user = User(username="rate-limit", password_hash="")
    db_session.add(user)
    db_session.commit()

    payload = {"message": "你好", "execution_preference": "react", "enable_debate": False}
    for i in range(10):
        resp = client.post("/api/v1/chat", json=payload)
        assert resp.status_code == 200, f"request {i + 1}: {resp.text}"

    blocked = client.post("/api/v1/chat", json=payload)
    assert blocked.status_code == 429
