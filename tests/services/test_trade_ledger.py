"""下沉后的交易台账服务 — 单元测试（upsert/sell/record 无需 HTTP）。"""

from datetime import date

import pytest

from stockresearch.core.exceptions import ValidationError
from stockresearch.db.models import Holding, Trade
from stockresearch.services.trade_ledger import (
    record_trade,
    sell_holding,
    upsert_holding,
)


def test_upsert_holding_creates_new(db_session) -> None:
    h = upsert_holding(
        db_session, user_id=1, symbol="600519", name="贵州茅台", cost_price=1800.0, quantity=100
    )
    assert h.id is not None
    assert h.quantity == 100
    row = db_session.query(Holding).filter_by(user_id=1, symbol="600519").one()
    assert float(row.cost_price) == 1800.0


def test_upsert_holding_averages_cost_on_add(db_session) -> None:
    upsert_holding(
        db_session, user_id=1, symbol="600519", name="贵州茅台", cost_price=1800.0, quantity=100
    )
    h2 = upsert_holding(
        db_session, user_id=1, symbol="600519", name="贵州茅台", cost_price=2000.0, quantity=100
    )
    assert h2.quantity == 200
    # 加权平均成本 = (1800*100 + 2000*100) / 200 = 1900
    assert float(h2.cost_price) == pytest.approx(1900.0)


def test_upsert_holding_updates_sector_and_buy_date(db_session) -> None:
    h = upsert_holding(
        db_session,
        user_id=1,
        symbol="600519",
        name="贵州茅台",
        cost_price=1800.0,
        quantity=100,
        sector="白酒",
        buy_date=date(2024, 5, 1),
    )
    assert h.sector == "白酒"
    assert h.buy_date == date(2024, 5, 1)


def test_sell_holding_reduces_quantity(db_session) -> None:
    upsert_holding(
        db_session, user_id=1, symbol="600519", name="贵州茅台", cost_price=1800.0, quantity=300
    )
    sell_holding(db_session, user_id=1, symbol="600519", quantity=100)
    h = db_session.query(Holding).filter_by(user_id=1, symbol="600519").one()
    assert h.quantity == 200


def test_sell_holding_deletes_when_zero(db_session) -> None:
    upsert_holding(
        db_session, user_id=1, symbol="600519", name="贵州茅台", cost_price=1800.0, quantity=100
    )
    sell_holding(db_session, user_id=1, symbol="600519", quantity=100)
    assert db_session.query(Holding).filter_by(user_id=1, symbol="600519").first() is None


def test_sell_holding_over_quantity_raises(db_session) -> None:
    upsert_holding(
        db_session, user_id=1, symbol="600519", name="贵州茅台", cost_price=1800.0, quantity=100
    )
    with pytest.raises(ValidationError, match="超出持仓"):
        sell_holding(db_session, user_id=1, symbol="600519", quantity=200)


def test_record_trade_attaches_latest_report(db_session) -> None:
    from stockresearch.db.models import ResearchReport

    upsert_holding(
        db_session, user_id=1, symbol="600519", name="贵州茅台", cost_price=1800.0, quantity=100
    )
    report = ResearchReport(user_id=1, symbol="600519", name="贵州茅台", report_json={})
    db_session.add(report)
    db_session.commit()

    t = record_trade(
        db_session,
        user_id=1,
        symbol="600519",
        name="贵州茅台",
        side="buy",
        price=1800.0,
        quantity=100,
        note="  决策备注  ",
    )
    assert t.report_id == report.id
    assert t.note == "决策备注"
    assert db_session.query(Trade).count() == 1
