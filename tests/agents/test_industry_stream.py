"""Industry Research Stream tests."""

import pytest

from stockresearch.agents.industry.stream import run_industry_research_stream
from stockresearch.core.schemas import ResearchReportOut


@pytest.mark.asyncio
async def test_industry_stream_builds_report_with_leaders(db_session) -> None:
    from stockresearch.services.local_user import get_or_create_mvp_user

    user = get_or_create_mvp_user(db_session)
    report: ResearchReportOut | None = None
    async for event in run_industry_research_stream(
        db_session,
        user.id,
        "半导体",
        "半导体行业深度研究",
    ):
        if event.get("type") == "done":
            raw = event.get("result")
            if isinstance(raw, dict):
                report = ResearchReportOut.model_validate(raw)

    assert report is not None
    assert report.sector == "半导体"
    assert len(report.dimensions) == 5
    assert "policy" in report.dimensions
    assert len(report.leaders) >= 1
    assert report.leaders[0].brief
