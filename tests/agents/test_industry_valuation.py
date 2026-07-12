"""Industry valuation dimension injects real PE when available."""

from __future__ import annotations

import pytest

from stockresearch.agents.industry.context import SectorResearchContext
from stockresearch.agents.industry.dimensions import build_valuation, prepare_valuation
from stockresearch.data.providers.sector import SectorLeader


@pytest.mark.asyncio
async def test_prepare_valuation_includes_pe_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    leaders = [
        SectorLeader(symbol="688981", name="中芯国际", change_pct=2.0, role="board_leader"),
        SectorLeader(symbol="002371", name="北方华创", change_pct=1.5, role="constituent"),
    ]

    async def fake_valuation(self, symbol: str) -> dict[str, object]:  # type: ignore[no-untyped-def]
        data = {
            "688981": {"pe_ttm": 45.0, "pb": 3.0, "pe_percentile": 0.6, "partial": False},
            "002371": {"pe_ttm": 35.0, "pb": 4.0, "pe_percentile": 0.4, "partial": False},
        }
        return data[symbol]

    monkeypatch.setattr(
        "stockresearch.data.providers.market.FinancialDataProvider.get_valuation",
        fake_valuation,
    )

    ctx = SectorResearchContext(
        sector="半导体",
        query="估值如何",
        llm=None,  # type: ignore[arg-type]
        user_id=1,
        db=None,  # type: ignore[arg-type]
        leaders=leaders,
    )
    _system, user, data = await prepare_valuation(ctx)
    assert "PE 45.0" in user or "PE 45" in user
    assert data["avg_pe"] == pytest.approx(40.0)
    assert data["pe_available"] == 2
    assert len(data["valuations"]) == 2  # type: ignore[arg-type]


def test_build_valuation_marks_gap_without_pe() -> None:
    result = build_valuation(
        {"leader_count": 2, "pe_available": 0, "avg_pe": None, "valuations": []},
        "",
    )
    assert result.partial is True
    assert "龙头估值 PE 不可用" in result.gaps
    assert result.confidence == "low"


def test_build_valuation_uses_avg_pe() -> None:
    result = build_valuation(
        {
            "leader_count": 2,
            "pe_available": 2,
            "avg_pe": 18.5,
            "valuations": [],
        },
        "估值偏合理。",
    )
    assert result.partial is False
    assert result.gaps == []
    assert "akshare_valuation" in result.data_sources
    assert result.score >= 5.5
