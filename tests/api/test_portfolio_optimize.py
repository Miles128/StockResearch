"""简单组合优化 API — POST /portfolio/optimize."""

from fastapi.testclient import TestClient


def _buy(client: TestClient, symbol: str = "600519", name: str = "贵州茅台", lots: int = 1) -> None:
    resp = client.post(
        "/api/v1/portfolio/holdings/transactions",
        json={
            "transactions": [
                {
                    "side": "buy",
                    "symbol": symbol,
                    "name": name,
                    "cost_price": 100.0,
                    "lots": lots,
                }
            ]
        },
    )
    assert resp.status_code == 200, resp.text


def _watch(client: TestClient, symbol: str, name: str) -> None:
    resp = client.post("/api/v1/portfolio/watchlist", json={"symbol": symbol, "name": name})
    assert resp.status_code == 200, resp.text


def _fake_optimize(monkeypatch, *, fail: bool = False) -> None:
    from stockresearch.core.schemas import PortfolioOptimizeOut, PortfolioOptimizeRow

    async def _fake_run(universe, *, method: str = "min_vol"):
        if fail:
            raise RuntimeError("boom")
        symbols = list(universe)
        return PortfolioOptimizeOut(
            method=method,
            method_label={"min_vol": "最小波动", "risk_parity": "风险平价", "balanced": "均衡"}.get(
                method, method
            ),
            rows=[
                PortfolioOptimizeRow(
                    symbol=s,
                    name=s,
                    current_weight=round(universe.get(s, 0.0), 4),
                    optimal_weight=round(1.0 / len(symbols), 4),
                )
                for s in symbols
            ],
            current_vol=30.0,
            current_return=8.0,
            optimal_vol=20.0,
            optimal_return=7.0,
            explanation="教育参考解释",
        )

    monkeypatch.setattr(
        "stockresearch.services.portfolio_optimizer.optimize_portfolio",
        _fake_run,
    )


def test_optimize_requires_two_symbols(client: TestClient) -> None:
    _buy(client)
    resp = client.post("/api/v1/portfolio/optimize", json={"method": "min_vol"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["partial"] is True
    assert "至少需要 2 个标的" in body["explanation"]


def test_optimize_min_vol_with_holdings_and_watchlist(client: TestClient, monkeypatch) -> None:
    _buy(client, symbol="600519")
    _buy(client, symbol="000858", name="五粮液")
    _watch(client, "300750", "宁德时代")
    _fake_optimize(monkeypatch)

    resp = client.post("/api/v1/portfolio/optimize", json={"method": "min_vol"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["method"] == "min_vol"
    assert len(body["rows"]) == 3
    rows = {r["symbol"]: r for r in body["rows"]}
    # 持仓有市值 → 当前权重非零；自选为 0
    assert rows["600519"]["current_weight"] > 0
    assert rows["300750"]["current_weight"] == 0
    assert abs(sum(r["optimal_weight"] for r in body["rows"]) - 1.0) < 1e-3
    assert "教育参考" in body["explanation"]


def test_optimize_balanced_method_passthrough(client: TestClient, monkeypatch) -> None:
    _buy(client, symbol="600519")
    _buy(client, symbol="000858", name="五粮液")
    _fake_optimize(monkeypatch)

    resp = client.post("/api/v1/portfolio/optimize", json={"method": "balanced"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["method"] == "balanced"
    assert resp.json()["method_label"] == "均衡"


def test_optimize_invalid_method(client: TestClient) -> None:
    resp = client.post("/api/v1/portfolio/optimize", json={"method": "yolo"})
    assert resp.status_code == 422
