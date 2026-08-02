"""Research streaming tests."""

import pytest

from stockresearch.agents.research.stream import _attach_deep_analysis, run_research_stream
from stockresearch.core.schemas import (
    DeepAnalysisOut,
    DimensionResult,
    ImpactOut,
    PricingBridgeOut,
    ResearchReportOut,
)
from stockresearch.utils.llm import MockLLMClient


@pytest.mark.asyncio
async def test_research_stream_emits_agents_debate_and_report() -> None:
    events: list[dict[str, object]] = []
    async for event in run_research_stream("600519", llm=MockLLMClient()):
        events.append(event)

    types = [str(e.get("type")) for e in events]
    assert types.count("agent_start") >= 7
    assert types.count("debate_round") == 3
    assert any(e.get("type") == "vote_tally" for e in events)
    assert any(e.get("type") == "manager" for e in events)
    assert "judge" in types
    assert types[-1] == "done"
    result = events[-1].get("result")
    assert isinstance(result, dict)
    assert result.get("symbol") == "600519"


def _deep_report() -> ResearchReportOut:
    return ResearchReportOut(
        symbol="600519",
        name="贵州茅台",
        dimensions={
            "fundamental": DimensionResult(
                agent="基本面",
                score=8.0,
                confidence="high",
                analysis="盈利稳健",
                highlights=["营收与净利双位数增长"],
                risks=["估值偏高"],
                data_sources=["mock"],
            ),
        },
        composite_score=8.0,
        composite_confidence="high",
        bias="bullish",
        summary="贵州茅台偏多。",
        analysis_depth="deep",
    )


@pytest.mark.asyncio
async def test_attach_deep_analysis_builds_thesis_for_deep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_impact(symbol: str) -> ImpactOut:
        return ImpactOut(
            window_trading_days=20,
            stock_return_pct=8.0,
            market_contrib_pct=3.0,
            industry_contrib_pct=1.0,
            idio_return_pct=4.0,
            partial=False,
            gaps=[],
        )

    async def fake_pricing(symbol: str, factors) -> PricingBridgeOut:
        return PricingBridgeOut(
            window_label="60d qfq",
            price_change_pct=10.0,
            earnings_contrib_pct=6.0,
            multiple_contrib_pct=4.0,
            factor_keys_used=["np_yoy"],
            partial=False,
        )

    monkeypatch.setattr(
        "stockresearch.services.impact.compute_impact", fake_impact
    )
    monkeypatch.setattr(
        "stockresearch.services.pricing_bridge.compute_pricing_bridge",
        fake_pricing,
    )

    report = _deep_report()
    await _attach_deep_analysis(report, "deep", "600519")

    assert report.deep_analysis is not None
    assert report.deep_analysis.impact is not None
    assert report.deep_analysis.pricing is not None
    assert report.deep_analysis.thesis is not None
    assert "偏多" in report.deep_analysis.thesis.claim
    assert "impact:idio" in report.deep_analysis.thesis.evidence_ids
    assert "pricing:bridge" in report.deep_analysis.thesis.evidence_ids


@pytest.mark.asyncio
async def test_attach_deep_analysis_skips_thesis_for_comprehensive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_impact(symbol: str) -> ImpactOut:
        return ImpactOut(window_trading_days=20, partial=False, gaps=[])

    monkeypatch.setattr(
        "stockresearch.services.impact.compute_impact", fake_impact
    )

    report = _deep_report()
    await _attach_deep_analysis(report, "comprehensive", "600519")

    assert report.deep_analysis is not None
    assert report.deep_analysis.impact is not None
    # comprehensive keeps Impact but does not get Pricing or Thesis
    assert report.deep_analysis.pricing is None
    assert report.deep_analysis.thesis is None
