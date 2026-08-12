"""Phase 12e Thesis 自动验证 — 单元测试（含起始价取端回归）。"""

from datetime import UTC, date, datetime

from stockresearch.db.models import ThesisVerification
from stockresearch.services.thesis_verification import _verify_one


def _bars(closes: list[float], start_date: str = "2026-01-01") -> list[dict[str, float | str]]:
    day = datetime.strptime(start_date, "%Y-%m-%d").date()
    from datetime import timedelta as td

    return [{"date": (day + td(days=i)).isoformat(), "close": c} for i, c in enumerate(closes)]


def _row(direction: str = "bullish", created: str = "2026-01-01") -> ThesisVerification:
    return ThesisVerification(
        user_id=1,
        report_id=None,
        symbol="600519",
        name="贵州茅台",
        claim="业绩可持续",
        direction=direction,
        horizon_days=60,
        created_at=datetime.strptime(created, "%Y-%m-%d").replace(tzinfo=UTC),
        due_at=date(2026, 3, 1),
        status="pending",
    )


def test_verify_bullish_challenged() -> None:
    row = _row(direction="bullish")
    _verify_one(row, _bars([100.0, 90.0]))
    assert row.status == "verified"
    assert "主张受挑战" in row.result_text


def test_verify_bullish_not_challenged() -> None:
    row = _row(direction="bullish")
    _verify_one(row, _bars([100.0, 105.0]))
    assert row.status == "verified"
    assert "未被证伪" in row.result_text


def test_verify_start_bar_nearest_before_created_at() -> None:
    """回归：验证窗起始价须取「最近一根 ≤ created_at」而非窗口最早一根。"""
    row = _row(direction="bullish", created="2026-02-26")
    # 02-24 起：预测日前 50→100（上涨），预测日后 100→92（下跌 -8%）
    bars = _bars(
        [50.0, 70.0, 100.0, 92.0, 92.0, 92.0, 92.0],
        start_date="2026-02-24",
    )
    _verify_one(row, bars)
    assert row.status == "verified"
    # 起始价 100（02-26），终点 92 → -8% ≤ -5% 阈值 → 受挑战
    assert "主张受挑战" in row.result_text


def test_verify_insufficient_bars() -> None:
    row = _row()
    _verify_one(row, _bars([100.0]))
    assert row.status == "verified"
    assert "数据不足" in row.result_text


def test_verify_not_due_skipped() -> None:
    row = _row()
    row.due_at = date(2099, 1, 1)
    _verify_one(row, _bars([100.0, 90.0]))
    assert row.status == "pending"
