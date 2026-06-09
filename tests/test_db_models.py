"""Tests for database models."""

import decimal
from datetime import date

from sqlalchemy import Numeric

from stockresearch.db.models import Conversation, Holding, User, WatchlistItem


def test_holding_cost_price_is_numeric() -> None:
    """Holding.cost_price should use Numeric, not float."""
    col = Holding.__table__.c.cost_price
    assert isinstance(col.type, Numeric)
    assert col.type.precision == 12
    assert col.type.scale == 4


def test_holding_with_decimal_cost_price(db_session) -> None:
    user = User(username="testuser", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    holding = Holding(
        user_id=user.id,
        symbol="600519",
        name="贵州茅台",
        cost_price=decimal.Decimal("1850.1234"),
        quantity=100,
        sector="消费",
        buy_date=date(2024, 1, 15),
    )
    db_session.add(holding)
    db_session.commit()

    fetched = db_session.query(Holding).first()
    assert fetched.cost_price == decimal.Decimal("1850.1234")
    assert isinstance(fetched.cost_price, decimal.Decimal)


def test_user_creation(db_session) -> None:
    user = User(username="alice", password_hash="secret")
    db_session.add(user)
    db_session.commit()

    fetched = db_session.query(User).first()
    assert fetched.username == "alice"
    assert fetched.password_hash == "secret"
    assert fetched.id is not None


def test_watchlist_item_creation(db_session) -> None:
    user = User(username="bob", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    item = WatchlistItem(user_id=user.id, symbol="000001", name="平安银行")
    db_session.add(item)
    db_session.commit()

    fetched = db_session.query(WatchlistItem).first()
    assert fetched.symbol == "000001"
    assert fetched.name == "平安银行"


def test_conversation_with_json_messages(db_session) -> None:
    user = User(username="carol", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    messages = [
        {"role": "user", "content": "分析贵州茅台"},
        {"role": "assistant", "content": "贵州茅台是白酒龙头…"},
    ]
    conv = Conversation(
        user_id=user.id,
        session_id="sess-001",
        messages=messages,
    )
    db_session.add(conv)
    db_session.commit()

    fetched = db_session.query(Conversation).first()
    assert len(fetched.messages) == 2
    assert fetched.messages[0]["role"] == "user"
    assert fetched.messages[1]["content"] == "贵州茅台是白酒龙头…"
