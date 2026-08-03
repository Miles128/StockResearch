"""Daily-scan briefing enhancements: sector ranking block + postmarket recap."""

import uuid
from datetime import date, datetime, time, timedelta

import pytest

from stockresearch.data.providers import sector as sector_mod
from stockresearch.data.providers.sector import SectorBoard
from stockresearch.db.models import BriefingRecord, User
from stockresearch.services.briefing import (
    _briefing_system_prompt,
    _collect_sector_block,
    _fallback_sections,
)
from stockresearch.services.briefing_scheduler import BriefingScheduler

_BOARDS = [
    SectorBoard(
        code="BK1",
        name="半导体",
        change_pct=3.2,
        leader_name="中芯国际",
        leader_symbol="688981",
        leader_change_pct=7.1,
    ),
    SectorBoard(
        code="BK2",
        name="白酒",
        change_pct=1.1,
        leader_name="贵州茅台",
        leader_symbol="600519",
        leader_change_pct=1.8,
    ),
    SectorBoard(
        code="BK3",
        name="券商",
        change_pct=0.5,
        leader_name="",
        leader_symbol="",
        leader_change_pct=0.0,
    ),
    SectorBoard(
        code="BK4",
        name="煤炭",
        change_pct=-1.2,
        leader_name="",
        leader_symbol="",
        leader_change_pct=0.0,
    ),
    SectorBoard(
        code="BK5",
        name="房地产开发",
        change_pct=-2.4,
        leader_name="—",
        leader_symbol="",
        leader_change_pct=0.0,
    ),
]


def _patch_boards(monkeypatch: pytest.MonkeyPatch, boards: list[SectorBoard]) -> None:
    async def _fake(self) -> list[SectorBoard]:
        return boards

    monkeypatch.setattr(sector_mod.SectorDataProvider, "fetch_industry_boards", _fake)


class _FakeHolding:
    def __init__(self, sector: str) -> None:
        self.sector = sector


async def test_sector_block_premarket_ranking_and_held_sector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_boards(monkeypatch, _BOARDS)
    block = await _collect_sector_block("premarket", [_FakeHolding("白酒")])  # type: ignore[arg-type]
    assert "上一交易日" in block
    assert "涨幅居前" in block and "跌幅居前" in block
    assert "半导体 +3.20%" in block and "领涨 中芯国际" in block
    assert "房地产开发 -2.40%" in block
    assert "持仓相关行业：白酒 +1.10%" in block


async def test_sector_block_intraday_uses_today_label(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_boards(monkeypatch, _BOARDS)
    block = await _collect_sector_block("postmarket", [])
    assert "今日" in block and "上一交易日" not in block


async def test_sector_block_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_boards(monkeypatch, [])
    block = await _collect_sector_block("premarket", [])
    assert "行业板块数据暂不可用" in block


def test_premarket_prompt_requires_focus_points() -> None:
    prompt = _briefing_system_prompt("premarket")
    assert "今日关注" in prompt
    assert "不给买卖建议" in prompt


def test_postmarket_prompt_recap_only_with_premarket_view() -> None:
    without = _briefing_system_prompt("postmarket")
    assert "逐条对照" not in without
    with_view = _briefing_system_prompt("postmarket", has_premarket_view=True)
    assert "逐条对照" in with_view and "盘前" in with_view


def test_fallback_sections_include_sector_block() -> None:
    _, sections = _fallback_sections(
        kind="postmarket",
        holdings_block="【持仓表现】\n- 示例",
        holding_news=[],
        sector_news=[],
        market_news=[],
        market_block="【大盘概况】\n指数数据暂不可用",
        alerts=[],
        sector_block="【行业板块（今日）】\n涨幅居前：\n- 半导体 +3.20%",
    )
    titles = [s.title for s in sections]
    assert "行业板块" in titles
    sector_section = sections[titles.index("行业板块")]
    assert "半导体" in sector_section.content
    assert "【行业板块" not in sector_section.content


def test_fallback_sections_omit_sector_block_when_empty() -> None:
    _, sections = _fallback_sections(
        kind="intraday",
        holdings_block="【持仓表现】\n- 示例",
        holding_news=[],
        sector_news=[],
        market_news=[],
        market_block="【大盘概况】\n指数数据暂不可用",
        alerts=[],
        sector_block="",
    )
    assert "行业板块" not in [s.title for s in sections]


@pytest.fixture()
def user(db_session):
    u = User(username=f"brief-{uuid.uuid4().hex[:8]}", password_hash="x")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def _day_bounds() -> tuple[datetime, datetime]:
    today = date.today()
    return datetime.combine(today, time.min), datetime.combine(today, time.max)


def test_morning_view_returns_summary_and_sections(db_session, user) -> None:
    start, end = _day_bounds()
    db_session.add(
        BriefingRecord(
            user_id=user.id,
            kind="premarket",
            title="盘前简报",
            summary="关注半导体链与北向动向",
            sections=[
                {"title": "持仓表现", "content": "茅台盘前参考价为昨收"},
                {"title": "综合结论", "content": "留意白酒板块强弱"},
            ],
            generated_at=datetime.now() - timedelta(minutes=1),
        )
    )
    db_session.commit()

    view = BriefingScheduler._morning_view(db_session, user.id, start, end)
    assert view is not None
    assert "关注半导体链与北向动向" in view
    assert "持仓表现：茅台盘前参考价为昨收" in view
    assert "综合结论：留意白酒板块强弱" in view


def test_morning_view_none_without_premarket(db_session, user) -> None:
    start, end = _day_bounds()
    assert BriefingScheduler._morning_view(db_session, user.id, start, end) is None
