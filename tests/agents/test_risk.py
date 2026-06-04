"""Risk engine tests."""

import pytest

from stockresearch.agents.risk.engine import run_risk_checkup
from stockresearch.db.models import Holding
from stockresearch.utils.llm import MockLLMClient


@pytest.mark.asyncio
async def test_stop_loss_red_alert() -> None:
    holdings = [
        Holding(
            id=1,
            user_id=1,
            symbol="300750",
            name="宁德时代",
            cost_price=250.0,
            quantity=100,
            sector="新能源",
        )
    ]
    result = await run_risk_checkup(holdings, llm=MockLLMClient())
    rule_ids = [a.rule_id for a in result.alerts]
    assert "stop_loss_red" in rule_ids


@pytest.mark.asyncio
async def test_empty_holdings_message() -> None:
    result = await run_risk_checkup([], llm=MockLLMClient())
    assert "录入" in result.portfolio_summary


@pytest.mark.asyncio
async def test_llm_analysis_present() -> None:
    holdings = [
        Holding(
            id=1,
            user_id=1,
            symbol="300750",
            name="宁德时代",
            cost_price=250.0,
            quantity=100,
            sector="新能源",
        )
    ]
    result = await run_risk_checkup(holdings, llm=MockLLMClient())
    assert result.llm_analysis is not None
    assert result.llm_analysis.market_assessment != ""
    assert result.llm_analysis.risk_narrative != ""


@pytest.mark.asyncio
async def test_llm_analysis_empty_holdings() -> None:
    result = await run_risk_checkup([], llm=MockLLMClient())
    assert result.llm_analysis is not None
    assert result.llm_analysis.correlation_analysis == "持仓不足两只，无需分析相关性。"
