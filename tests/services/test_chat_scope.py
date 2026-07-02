"""ChatContextScope and portfolio routing tests."""

import pytest
from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.chat_execute import execute_chat_turn
from stockresearch.agents.orchestrator.react_agent import OrchestratorAgent
from stockresearch.core.schemas import ChatUserContext, ModeSettingsOut
from stockresearch.db.models import Holding, User
from stockresearch.services.chat_scope import (
    PORTFOLIO_TOOL_NAMES,
    build_chat_context_scope,
    resolve_subject_symbol,
    should_run_portfolio_risk_shortcut,
)
from stockresearch.utils.llm import MockLLMClient


class _HoldingStub:
    symbol = "600519"
    name = "贵州茅台"
    sector = "白酒"
    float_cost_price = 1800.0
    quantity = 10


def test_stock_risk_does_not_shortcut_portfolio_checkup() -> None:
    ctx = build_chat_context_scope("600519有什么风险", [_HoldingStub()], None)  # type: ignore[list-item]
    assert not ctx.run_portfolio_risk_shortcut
    assert not ctx.include_holdings


def test_portfolio_risk_shortcut_when_explicit() -> None:
    ctx = build_chat_context_scope("我的持仓风险大吗", [_HoldingStub()], None)  # type: ignore[list-item]
    assert ctx.run_portfolio_risk_shortcut
    assert ctx.include_holdings


def test_resolve_subject_from_ui_context() -> None:
    ui = ChatUserContext(kind="stock", label="贵州茅台 600519", symbol="600519")
    sym, name = resolve_subject_symbol("为什么涨", user_context=ui)
    assert sym == "600519"
    assert name == "贵州茅台"


def test_should_run_portfolio_risk_shortcut_risk_tab_vague() -> None:
    ui = ChatUserContext(kind="risk", label="风控")
    assert should_run_portfolio_risk_shortcut("风险大吗", ui, include_holdings=True)


@pytest.mark.asyncio
async def test_sector_holdings_tool_blocked_without_portfolio_context(
    db_session: Session,
) -> None:
    user = User(username="scope-tool", password_hash="")
    db_session.add(user)
    db_session.commit()

    agent = OrchestratorAgent(
        db_session,
        MockLLMClient(),
        user_id=user.id,
        portfolio_context=False,
        holdings=[],
    )
    result = await agent._execute_tool("get_sector_holdings", {"sector": "白酒"})
    assert "不可用" in result
    assert "get_sector_holdings" in PORTFOLIO_TOOL_NAMES


@pytest.mark.asyncio
async def test_sector_holdings_uses_scoped_holdings_only(db_session: Session) -> None:
    user = User(username="scope-hold", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add(
        Holding(
            user_id=user.id,
            symbol="600519",
            name="贵州茅台",
            cost_price=1800.0,
            quantity=10,
            sector="白酒",
        )
    )
    db_session.add(
        Holding(
            user_id=user.id,
            symbol="000001",
            name="平安银行",
            cost_price=10.0,
            quantity=100,
            sector="银行",
        )
    )
    db_session.commit()

    scoped = db_session.query(Holding).filter(Holding.symbol == "600519").all()
    agent = OrchestratorAgent(
        db_session,
        MockLLMClient(),
        user_id=user.id,
        portfolio_context=True,
        holdings=scoped,
    )
    result = await agent._execute_tool("get_sector_holdings", {"sector": "白酒"})
    assert "600519" in result
    assert "000001" not in result


@pytest.mark.asyncio
async def test_stock_risk_question_uses_react_not_portfolio_checkup(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(username="scope-risk", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add(
        Holding(
            user_id=user.id,
            symbol="600519",
            name="贵州茅台",
            cost_price=1800.0,
            quantity=10,
            sector="白酒",
        )
    )
    db_session.commit()

    risk_called = False

    async def _fake_risk(*args: object, **kwargs: object) -> object:
        nonlocal risk_called
        risk_called = True
        raise AssertionError("portfolio risk should not run")

    monkeypatch.setattr(
        "stockresearch.agents.orchestrator.chat_execute._run_risk_sync",
        _fake_risk,
    )

    holdings = db_session.query(Holding).filter(Holding.user_id == user.id).all()
    scope = build_chat_context_scope("600519有什么风险", holdings, None)
    result = await execute_chat_turn(
        db=db_session,
        user_id=user.id,
        message="600519有什么风险",
        llm=MockLLMClient(),
        holdings=holdings,
        debate_on=False,
        master_on=False,
        mode_settings=ModeSettingsOut(),
        scope=scope,
    )
    assert not risk_called
    assert result.intent != "risk" or not result.cards
