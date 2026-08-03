"""POST /research/refill route tests."""

from unittest.mock import AsyncMock, patch

from stockresearch.core.schemas import DimensionResult, ResearchReportOut


def _sample_report(data_gaps: list[str] | None = None) -> ResearchReportOut:
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
        summary="贵州茅台综合偏多。",
        data_gaps=data_gaps or [],
    )


def test_refill_with_explicit_gaps_reruns_research(client, db_session) -> None:
    report = _sample_report()
    with (
        patch(
            "stockresearch.api.routes.research.run_research",
            new=AsyncMock(return_value=report),
        ) as mock_run,
        patch("stockresearch.api.routes.research.evict_gap_caches") as mock_evict,
    ):
        resp = client.post(
            "/api/v1/research/refill",
            json={"symbol": "600519", "gaps": ["公告仅标题", "财务序列不完整"]},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "600519"
    assert body["id"] is not None
    mock_run.assert_awaited_once()
    mock_evict.assert_called_once_with("600519", ["announcements", "financial"])


def test_refill_falls_back_to_latest_report_gaps(client, db_session) -> None:
    from stockresearch.api.routes.research import persist_report
    from stockresearch.services.local_user import get_or_create_mvp_user

    user = get_or_create_mvp_user(db_session)
    persist_report(db_session, user.id, _sample_report(data_gaps=["个股新闻为空"]))
    db_session.commit()

    report = _sample_report()
    with (
        patch(
            "stockresearch.api.routes.research.run_research",
            new=AsyncMock(return_value=report),
        ),
        patch("stockresearch.api.routes.research.evict_gap_caches") as mock_evict,
    ):
        resp = client.post("/api/v1/research/refill", json={"symbol": "600519"})
    assert resp.status_code == 200
    mock_evict.assert_called_once_with("600519", ["news_sentiment"])


def test_refill_rejects_invalid_symbol(client, db_session) -> None:
    resp = client.post("/api/v1/research/refill", json={"symbol": "12345"})
    assert resp.status_code == 422
