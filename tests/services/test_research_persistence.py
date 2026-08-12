"""Portfolio summary / research persistence — 下沉服务的单元测试。"""

from datetime import date

from stockresearch.core.schemas import ResearchReportOut
from stockresearch.db.models import Holding
from stockresearch.services.portfolio_summary import build_portfolio_brief
from stockresearch.services.research_persistence import (
    register_cached_report,
    register_report_verifications,
)


def _holding(symbol: str, name: str, cost: float, qty: int, sector: str = "科技") -> Holding:
    return Holding(
        user_id=1,
        symbol=symbol,
        name=name,
        cost_price=cost,
        quantity=qty,
        sector=sector,
        buy_date=date(2024, 5, 1),
    )


def _report(symbol: str = "600519") -> ResearchReportOut:
    return ResearchReportOut(
        symbol=symbol,
        name="贵州茅台",
        dimensions={},
        composite_score=6.5,
        composite_confidence="medium",  # type: ignore[arg-type]
        bias="bullish",  # type: ignore[arg-type]
        summary="综合四维看，短期偏强。",
        disclaimer="以上内容由 AI 生成，仅供参考，不构成投资建议。",
    )


def test_build_portfolio_brief_empty() -> None:
    brief = build_portfolio_brief([])
    assert brief["count"] == 0
    assert brief["total_cost"] == 0.0
    assert brief["holdings"] == []


def test_build_portfolio_brief_aggregates() -> None:
    brief = build_portfolio_brief(
        [
            _holding("600519", "贵州茅台", 1800.0, 100, sector="白酒"),
            _holding("300750", "宁德时代", 200.0, 500, sector="新能源"),
            _holding("000858", "五粮液", 150.0, 200, sector="白酒"),
        ]
    )
    assert brief["count"] == 3
    assert brief["total_cost"] == 1800.0 * 100 + 200.0 * 500 + 150.0 * 200
    assert brief["total_quantity"] == 800
    assert brief["sectors"][0] == {"name": "白酒", "count": 2}
    assert brief["holdings"][0]["buy_date"] == "2024-05-01"


def test_register_report_verifications_idempotent(db_session) -> None:
    from stockresearch.db.models import Prediction, ResearchReport

    report = _report()
    row = ResearchReport(user_id=1, symbol=report.symbol, name=report.name, report_json={})
    db_session.add(row)
    db_session.commit()

    register_report_verifications(db_session, 1, report, report_id=row.id)
    register_report_verifications(db_session, 1, report, report_id=row.id)
    preds = db_session.query(Prediction).filter_by(report_id=row.id).all()
    assert len(preds) == 1  # 幂等：同一报告只登记一次


def test_register_cached_report_reuses_latest_row(db_session) -> None:
    from stockresearch.db.models import Prediction, ResearchReport

    report = _report()
    row = ResearchReport(user_id=1, symbol=report.symbol, name=report.name, report_json={})
    db_session.add(row)
    db_session.commit()

    report_id = register_cached_report(db_session, 1, report)
    assert report_id == row.id  # 复用已有报告行，不新建
    assert db_session.query(ResearchReport).count() == 1
    preds = db_session.query(Prediction).filter_by(report_id=row.id).all()
    assert len(preds) == 1


def test_register_cached_report_creates_row_when_none(db_session) -> None:
    from stockresearch.db.models import Prediction, ResearchReport

    report = _report()
    report_id = register_cached_report(db_session, 1, report)
    assert report_id is not None
    assert db_session.query(ResearchReport).count() == 1
    preds = db_session.query(Prediction).filter_by(report_id=report_id).all()
    assert len(preds) == 1
