"""Industry Research Stream tests."""

import pytest

from stockresearch.agents.industry.stream import run_industry_research_stream
from stockresearch.core.schemas import ResearchReportOut
from stockresearch.data.providers.sector import SectorLeader


@pytest.mark.asyncio
async def test_industry_stream_builds_report_with_leaders(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from stockresearch.services.local_user import get_or_create_mvp_user

    # 注入确定性的板块龙头，避免依赖外网
    async def fake_leaders(self, _sector: str, *, limit: int = 3) -> list[SectorLeader]:
        return [
            SectorLeader(symbol="688981", name="中芯国际", change_pct=2.1, role="board_leader"),
            SectorLeader(symbol="002371", name="北方华创", change_pct=1.8, role="board_leader"),
        ][:limit]

    from stockresearch.data.providers import sector as sector_mod

    monkeypatch.setattr(sector_mod.SectorDataProvider, "get_sector_leaders", fake_leaders)

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
