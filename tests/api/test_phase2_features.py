"""Phase 2 feature API tests."""

from stockresearch.core.schemas import DebateResult, DimensionResult, ResearchReportOut
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
        debate=DebateResult(
            rounds=[],
            judge_verdict="偏多",
            consensus="偏多",
            core_divergence="分歧中等",
            final_bias="bullish",
            confidence="medium",
        ),
    )


def test_report_to_pdf_bytes(client, db_session) -> None:
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


def test_memory_search(client, db_session) -> None:
    from stockresearch.api.routes.research import persist_report
    from stockresearch.services.local_user import get_or_create_mvp_user

    user = get_or_create_mvp_user(db_session)
    persist_report(db_session, user.id, _sample_report())

    local = search_research_memory(db_session, user.id, "白酒")
    assert len(local.hits) == 1

    resp = client.get("/api/v1/research/memory/search?q=白酒")
    assert resp.status_code == 200
    assert len(resp.json()["hits"]) == 1


def test_signal_backtest_endpoint(client, db_session) -> None:
    from stockresearch.api.routes.research import persist_report
    from stockresearch.services.local_user import get_or_create_mvp_user

    user = get_or_create_mvp_user(db_session)
    persist_report(db_session, user.id, _sample_report())

    resp = client.get("/api/v1/research/signal-backtest")
    assert resp.status_code == 200
    body = resp.json()
    assert "horizons" in body
    assert len(body["horizons"]) == 3


def test_briefing_generate(client) -> None:
    resp = client.post("/api/v1/briefing/generate?kind=morning")
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "morning"
    assert body["sections"]


def test_industry_research_endpoint(client, db_session) -> None:
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
