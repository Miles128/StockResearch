"""Tests for price alert dedupe logic."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from stockresearch.db.models import Holding, PriceAlertNotification, PriceAlertSetting, User, WatchlistItem
from stockresearch.services.price_alerts import check_price_alerts_for_user, get_or_create_settings


@pytest.fixture
def user(db_session):
    u = User(username=f"alert-{uuid.uuid4().hex[:8]}", password_hash="x")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def test_get_or_create_settings(db_session, user) -> None:
    row = get_or_create_settings(db_session, user.id)
    assert row.enabled is True
    assert float(row.threshold_pct) == 5.0
    again = get_or_create_settings(db_session, user.id)
    assert again.id == row.id


@pytest.mark.asyncio
async def test_price_alert_dedupes_same_day(db_session, user) -> None:
    db_session.add(
        Holding(
            user_id=user.id,
            symbol="600519",
            name="贵州茅台",
            cost_price=1000,
            quantity=100,
            sector="白酒",
        )
    )
    db_session.add(PriceAlertSetting(user_id=user.id, enabled=True, threshold_pct=3.0))
    db_session.commit()

    quote = MagicMock(symbol="600519", name="贵州茅台", change_pct=4.5)

    with patch(
        "stockresearch.services.price_alerts.BatchQuoteProvider"
    ) as provider_cls:
        provider_cls.return_value.get_quotes = AsyncMock(return_value=[quote])
        created = await check_price_alerts_for_user(db_session, user.id)
        assert created == 1

        created_again = await check_price_alerts_for_user(db_session, user.id)
        assert created_again == 0

    rows = db_session.query(PriceAlertNotification).filter_by(user_id=user.id).all()
    assert len(rows) == 1
    assert rows[0].symbol == "600519"
    assert rows[0].trading_date == date.today()


@pytest.mark.asyncio
async def test_price_alert_includes_watchlist(db_session, user) -> None:
    db_session.add(WatchlistItem(user_id=user.id, symbol="000001", name="平安银行"))
    db_session.add(PriceAlertSetting(user_id=user.id, enabled=True, threshold_pct=2.0))
    db_session.commit()

    quote = MagicMock(symbol="000001", name="平安银行", change_pct=-2.5)

    with patch(
        "stockresearch.services.price_alerts.BatchQuoteProvider"
    ) as provider_cls:
        provider_cls.return_value.get_quotes = AsyncMock(return_value=[quote])
        created = await check_price_alerts_for_user(db_session, user.id)
        assert created == 1
