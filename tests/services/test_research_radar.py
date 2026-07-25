"""Research radar rule signals."""

import uuid
from datetime import UTC, datetime, timedelta

from stockresearch.db.models import Holding, ResearchReport, User
from stockresearch.services.research_radar import collect_research_radar_signals


def test_radar_detects_bias_flip(db_session) -> None:
    user = User(username=f"radar-{uuid.uuid4().hex[:8]}", password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(
        Holding(
            user_id=user.id,
            symbol="600519",
            name="贵州茅台",
            cost_price=1600,
            quantity=100,
            sector="白酒",
        )
    )
    t0 = datetime.now(UTC) - timedelta(days=10)
    t1 = datetime.now(UTC) - timedelta(days=1)
    db_session.add_all(
        [
            ResearchReport(
                user_id=user.id,
                symbol="600519",
                name="贵州茅台",
                report_json={"bias": "bullish", "composite_score": 7.0, "summary": "a"},
                created_at=t0,
            ),
            ResearchReport(
                user_id=user.id,
                symbol="600519",
                name="贵州茅台",
                report_json={"bias": "bearish", "composite_score": 4.0, "summary": "b"},
                created_at=t1,
            ),
        ]
    )
    db_session.commit()

    holdings = db_session.query(Holding).filter(Holding.user_id == user.id).all()
    signals = collect_research_radar_signals(db_session, user.id, holdings)
    assert len(signals) == 1
    assert signals[0].type == "research"
    assert "转向" in signals[0].title
