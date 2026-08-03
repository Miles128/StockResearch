"""Market-level dimension tests — macro enrichment with overseas + macro data."""

from datetime import UTC, datetime

import pytest

from stockresearch.agents.market.context import MarketResearchContext
from stockresearch.agents.market.dimensions import (
    build_macro,
    format_enrichment_block,
    prepare_macro,
)
from stockresearch.core.schemas import IndexQuoteOut, MarketOverviewOut


def _overview() -> MarketOverviewOut:
    return MarketOverviewOut(
        indices=[
            IndexQuoteOut(name="上证指数", symbol="000001", price=3200.0, change_pct=0.5),
            IndexQuoteOut(name="深证成指", symbol="399001", price=10500.0, change_pct=-0.3),
        ],
        northbound_net_yi=12.5,
        advancers=2800,
        decliners=1900,
        source="sina",
        data_status="live",
        message=None,
        updated_at=datetime.now(UTC),
    )


def _ctx(**overrides: object) -> MarketResearchContext:
    overview = _overview()
    base: dict[str, object] = {
        "query": "今天大盘怎么看",
        "llm": None,
        "overview": overview,
        "overview_text": "上证指数: 3200.00 ↑ +0.50%",
    }
    base.update(overrides)
    return MarketResearchContext(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_prepare_macro_includes_overseas_and_macro_blocks() -> None:
    ctx = _ctx(
        global_text="恒生指数: 26009.40 ↑ +0.48%",
        macro_text="【宏观数据(Kimi, 2026-08-01)】\n- CPI 同比: 0.4%(2026-06)",
        global_changes=[0.48, 0.65],
    )
    system, user, data = await prepare_macro(ctx)
    assert "海外市场联动" in system
    assert "【外围市场】" in user
    assert "恒生指数: 26009.40 ↑ +0.48%" in user
    assert "【宏观数据(Kimi, 2026-08-01)】" in user
    assert data["global_changes"] == [0.48, 0.65]


@pytest.mark.asyncio
async def test_prepare_macro_degrades_when_enrichment_missing() -> None:
    ctx = _ctx()
    system, user, data = await prepare_macro(ctx)
    assert "宏观指标与外围市场数据暂不可用" in user
    assert data["global_changes"] == []


def test_format_enrichment_block() -> None:
    block = format_enrichment_block("恒生指数: 26009.40 ↑ +0.48%", "【宏观数据(Kimi)】")
    assert block.startswith("【外围市场】")
    assert "【宏观数据(Kimi)】" in block
    assert format_enrichment_block("", "") == ""


def test_build_macro_sources_and_global_data_passthrough() -> None:
    result = build_macro(
        {
            "index_changes": [0.5, -0.3],
            "northbound_net_yi": 12.5,
            "advancers": 2800,
            "global_changes": [0.48, 0.65],
        },
        "分析文本",
    )
    assert result.agent == "macro"
    assert "global_indices" in result.data_sources
    assert "kimi_macro" in result.data_sources
