"""Research report history and export tests."""

from stockresearch.core.schemas import DebateResult, DimensionResult, ResearchReportOut
from stockresearch.services.report_export import report_to_markdown


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
        summary="贵州茅台综合偏多。",
        debate=DebateResult(
            rounds=[],
            judge_verdict="偏多",
            consensus="偏多",
            core_divergence="分歧中等",
            final_bias="bullish",
            confidence="medium",
        ),
    )


def test_list_and_export_reports(client, db_session) -> None:
    from stockresearch.api.routes.research import persist_report
    from stockresearch.services.auth import get_or_create_mvp_user

    user = get_or_create_mvp_user(db_session)
    row = persist_report(db_session, user.id, _sample_report())

    listed = client.get("/api/v1/research/reports")
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["symbol"] == "600519"
    assert items[0]["has_debate"] is True

    detail = client.get(f"/api/v1/research/reports/{row.id}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "贵州茅台"

    md = client.get(f"/api/v1/research/reports/{row.id}/markdown")
    assert md.status_code == 200
    assert "贵州茅台" in md.text
    assert "多空辩论" in md.text


def test_report_to_markdown_includes_dimensions() -> None:
    md = report_to_markdown(_sample_report())
    assert "四维分析" in md
    assert "盈利稳健" in md
