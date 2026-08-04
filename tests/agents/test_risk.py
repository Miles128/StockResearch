"""Risk engine tests."""

import pytest

from stockresearch.agents.risk.engine import run_risk_checkup
from stockresearch.db.models import Holding
from stockresearch.services.mock_llm import MockLLMClient


@pytest.mark.asyncio
async def test_stop_loss_red_alert(monkeypatch) -> None:
    from datetime import UTC, datetime

    from stockresearch.data.providers.market import Quote, QuoteProvider

    async def fake_get_quotes(
        self, symbols: list[str], *, cache_ttl_seconds: int | None = None
    ) -> dict[str, Quote]:
        return {
            sym: Quote(
                symbol=sym,
                name="宁德时代",
                price=200.0,
                change_pct=-2.0,
                open=205.0,
                high=210.0,
                low=198.0,
                volume=10000.0,
                updated_at=datetime.now(UTC),
            )
            for sym in symbols
        }

    monkeypatch.setattr(QuoteProvider, "get_quotes", fake_get_quotes)

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


@pytest.mark.asyncio
async def test_disable_llm_analysis_skips_llm_and_keeps_rules(monkeypatch) -> None:
    """PRD §四: 规则引擎 + 可选 LLM 解读。

    enable_llm_analysis=False 时：
    1. 不调用 LLM (MockLLMClient.complete 不应被调用)
    2. llm_analysis 为 None
    3. 规则告警仍然产出
    4. human_message 直接复用规则 message
    """
    from datetime import UTC, datetime

    from stockresearch.data.providers.market import Quote, QuoteProvider

    async def fake_get_quotes(
        self, symbols: list[str], *, cache_ttl_seconds: int | None = None
    ) -> dict[str, Quote]:
        return {
            "300750": Quote(
                symbol="300750",
                name="宁德时代",
                price=200.0,
                change_pct=-2.0,
                open=205.0,
                high=210.0,
                low=198.0,
                volume=10000.0,
                updated_at=datetime.now(UTC),
            )
        }

    monkeypatch.setattr(QuoteProvider, "get_quotes", fake_get_quotes)

    llm = MockLLMClient()

    # 验证 LLM 真的不被调用：若被调用则抛错让测试失败
    async def _fail_if_called(system: str, user: str) -> str:
        raise AssertionError("LLM.complete was called despite enable_llm_analysis=False")

    llm.complete = _fail_if_called  # type: ignore[assignment]

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
    result = await run_risk_checkup(holdings, llm=llm, enable_llm_analysis=False)

    # 规则告警仍存在
    assert any(a.rule_id == "stop_loss_red" for a in result.alerts)
    # LLM 被关闭
    assert result.llm_analysis is None
    # human_message 直接复用规则原文
    for alert in result.alerts:
        assert alert.human_message == alert.message
