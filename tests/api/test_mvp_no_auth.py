"""MVP no-auth API tests."""

from fastapi.testclient import TestClient


def test_chat_works_without_auth(client: TestClient) -> None:
    resp = client.post("/api/v1/chat", json={"message": "你好"})
    assert resp.status_code == 200
    assert "reply" in resp.json()


def test_holdings_work_without_auth(client: TestClient) -> None:
    resp = client.get("/api/v1/portfolio/holdings")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
