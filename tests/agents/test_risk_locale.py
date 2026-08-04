"""Risk checkup locale tests."""

import pytest

from stockresearch.agents.risk.engine import run_risk_checkup
from stockresearch.core.output_style import output_style_scope


@pytest.mark.asyncio
async def test_risk_checkup_empty_holdings_english_summary() -> None:
    with output_style_scope(locale="en"):
        result = await run_risk_checkup([], llm=None)
    assert "holdings" in result.portfolio_summary.lower()
    assert "录入" not in result.portfolio_summary
