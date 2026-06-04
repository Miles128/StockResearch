"""Orchestrator holdings integration tests."""

import pytest
from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.graph import Orchestrator
from stockresearch.db.models import Holding, User
from stockresearch.services.auth import hash_password


@pytest.mark.asyncio
async def test_chat_risk_sees_user_holdings(db_session: Session) -> None:
    user = User(username="holdings_user", password_hash=hash_password("password1"))
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

    orchestrator = Orchestrator(db_session)
    resp = await orchestrator.run(user.id, "我的持仓风险大吗")

    assert resp.intent == "risk"
    assert "还没有录入持仓" not in resp.reply
    assert "未检测到持仓" not in resp.reply
    risk_cards = [c for c in resp.cards if c.type == "risk"]
    assert risk_cards
    summary = str(risk_cards[0].data.get("portfolio_summary", ""))
    assert "1 只持仓" in summary or "风险" in summary
