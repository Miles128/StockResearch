"""Phase 2 feature API tests."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from stockresearch.core.schemas import (
    AshareFactorOut,
    DimensionResult,
    FactorSourceOut,
    ResearchReportOut,
)
from stockresearch.services.report_export import report_to_markdown, report_to_pdf
from stockresearch.services.research_memory import search_research_memory


def _sample_report() -> ResearchReportOut:
    return ResearchReportOut(
        symbol="600519",
        name="贵州茅台",
        dimensions={
            "fundamental": DimensionResult(
                agent="fundamental",
                score=7.5,
                confidence="high",
                highlights=["盈利稳健"],
                risks=["估值偏高"],
                data_sources=["akshare_financials"],
            )
        },
        composite_score=7.5,
        composite_confidence="high",
        bias="bullish",
        summary="贵州茅台综合偏多，白酒板块景气度尚可。",
        ashare_factors=[
            AshareFactorOut(
                category="资金与筹码",
                name="龙虎榜与游资席位",
                status="verified",
                impact="sentiment",
                evidence=["龙虎榜数据：akshare_lhb"],
                source_details=[
                    FactorSourceOut(
                        key="akshare_lhb",
                        label="龙虎榜",
                        layer="L2",
                        provider="akshare",
                        status="verified",
                    )
                ],
            )
        ],
    )


def test_report_to_pdf_bytes(client: TestClient, db_session: Session) -> None:
    from stockresearch.api.routes.research import persist_report
    from stockresearch.services.local_user import get_or_create_mvp_user

    pdf = report_to_pdf(_sample_report())
    assert pdf[:4] == b"%PDF"

    user = get_or_create_mvp_user(db_session)
    row = persist_report(db_session, user.id, _sample_report())
    resp = client.get(f"/api/v1/research/reports/{row.id}/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


def test_report_markdown_includes_ashare_factors() -> None:
    md = report_to_markdown(_sample_report())
    assert "A 股因子检查" in md
    assert "龙虎榜与游资席位" in md
    assert "L2/akshare/龙虎榜/verified" in md


def test_memory_search(client: TestClient, db_session: Session) -> None:
    from stockresearch.api.routes.research import persist_report
    from stockresearch.services.local_user import get_or_create_mvp_user

    user = get_or_create_mvp_user(db_session)
    persist_report(db_session, user.id, _sample_report())

    local = search_research_memory(db_session, user.id, "白酒")
    assert len(local.hits) == 1

    resp = client.get("/api/v1/research/memory/search?q=白酒")
    assert resp.status_code == 200
    assert len(resp.json()["hits"]) == 1


def test_signal_backtest_endpoint(client: TestClient, db_session: Session) -> None:
    from stockresearch.api.routes.research import persist_report
    from stockresearch.services.local_user import get_or_create_mvp_user

    user = get_or_create_mvp_user(db_session)
    persist_report(db_session, user.id, _sample_report())

    resp = client.get("/api/v1/research/signal-backtest")
    assert resp.status_code == 200
    body = resp.json()
    assert "horizons" in body
    assert len(body["horizons"]) == 3


def test_briefing_generate(client: TestClient) -> None:
    resp = client.post("/api/v1/briefing/generate?kind=intraday", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "intraday"
    assert body["title"] == "盘中简报"
    assert body["sections"]
    titles = {s["title"] for s in body["sections"]}
    assert "综合结论" in titles or "持仓表现" in titles


def test_briefing_generate_premarket(client: TestClient) -> None:
    resp = client.post("/api/v1/briefing/generate?kind=premarket", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "premarket"
    assert body["title"] == "盘前简报"
    assert body["sections"]
    titles = {s["title"] for s in body["sections"]}
    assert "综合结论" in titles or "持仓表现" in titles


def test_industry_research_endpoint(client: TestClient, db_session: Session, monkeypatch) -> None:
    from stockresearch.data.providers.sector import SectorDataProvider, SectorLeader

    async def fake_leaders(self, _sector: str, *, limit: int = 3) -> list[SectorLeader]:
        return [
            SectorLeader(symbol="600519", name="贵州茅台", change_pct=1.2),
            SectorLeader(symbol="000858", name="五粮液", change_pct=0.8),
        ][:limit]

    monkeypatch.setattr(SectorDataProvider, "get_sector_leaders", fake_leaders)

    resp = client.post(
        "/api/v1/research/industry",
        json={"sector": "白酒", "query": "白酒板块深度研究"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "reply" in body
    assert "cards" in body
    research_cards = [c for c in body["cards"] if c.get("type") == "research"]
    assert research_cards
    data = research_cards[0]["data"]
    assert data.get("sector") == "白酒"
    assert len(data.get("leaders", [])) >= 1

    listed = client.get("/api/v1/research/reports")
    assert listed.status_code == 200
    assert any(item["name"] == "白酒" for item in listed.json())
