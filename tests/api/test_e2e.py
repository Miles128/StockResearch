"""API integration tests — 5 core user paths."""

import pytest
from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "disclaimer" in resp.json()


def test_root_not_404(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    content_type = resp.headers.get("content-type", "")
    if "application/json" in content_type:
        assert "app" in resp.json()
    else:
        assert "text/html" in content_type
        assert "root" in resp.text


def test_api_v1_index(client: TestClient) -> None:
    resp = client.get("/api/v1")
    assert resp.status_code == 200
    assert "endpoints" in resp.json()


def test_path_holdings(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/portfolio/holdings",
        json={
            "query": "600519",
            "cost_price": 1800.0,
            "quantity": 10,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "600519"
    assert "茅台" in data["name"]
    listing = client.get("/api/v1/portfolio/holdings")
    assert len(listing.json()) == 1


def test_path_holdings_by_name(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/portfolio/holdings",
        json={"query": "贵州茅台", "cost_price": 1800.0, "quantity": 5},
    )
    assert resp.status_code == 200
    assert resp.json()["symbol"] == "600519"


def test_market_overview(client: TestClient) -> None:
    resp = client.get("/api/v1/market/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["indices"]) >= 1
    assert data["data_status"] in ("live", "mock", "unavailable")
    if data["data_status"] == "live":
        sh = next(i for i in data["indices"] if i["name"] == "上证指数")
        assert sh["price"] > 1000, "上证指数点位应大于1000，若过低说明仍是假数据"


@pytest.mark.asyncio
async def test_path_research(client: TestClient) -> None:
    resp = client.get("/api/v1/research/analyze?symbol=600519")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "600519"
    assert "dimensions" in data
    assert "debate" in data
    assert data["debate"] is not None
    assert "disclaimer" in data


@pytest.mark.asyncio
async def test_path_risk_checkup(client: TestClient) -> None:
    client.post(
        "/api/v1/portfolio/holdings",
        json={
            "symbol": "300750",
            "name": "宁德时代",
            "cost_price": 250.0,
            "quantity": 100,
            "sector": "新能源",
        },
    )
    resp = client.post("/api/v1/risk/checkup")
    assert resp.status_code == 200
    assert "alerts" in resp.json()


@pytest.mark.asyncio
async def test_path_chat_research(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/chat",
        json={"message": "帮我分析一下贵州茅台"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "chat"
    assert len(data["cards"]) >= 1
    assert "disclaimer" in data


@pytest.mark.asyncio
async def test_path_news_ingest_and_feed(client: TestClient) -> None:
    ingest = client.post("/api/v1/news/ingest?limit=5")
    assert ingest.status_code == 200
    feed = client.get("/api/v1/news/feed")
    assert feed.status_code == 200
