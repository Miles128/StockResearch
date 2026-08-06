"""Phase 12a 预测日记 — 提取 / 评分 / 统计单元测试。"""

from datetime import UTC, date, datetime, timedelta

import pytest

from stockresearch.core.schemas import ResearchReportOut
from stockresearch.db.models import Prediction
from stockresearch.services.prediction_journal import (
    _score_one,
    extract_prediction,
    prediction_stats,
)


def _report(bias: str = "bullish", confidence: str = "medium") -> ResearchReportOut:
    return ResearchReportOut(
        symbol="600519",
        name="贵州茅台",
        dimensions={},
        composite_score=6.5,
        composite_confidence=confidence,  # type: ignore[arg-type]
        bias=bias,  # type: ignore[arg-type]
        summary="综合四维看，短期偏强，估值分位偏高。",
        disclaimer="以上内容由 AI 生成，仅供参考，不构成投资建议。",
    )


def test_extract_prediction_uses_report_fact_layer() -> None:
    p = extract_prediction(
        _report(bias="bearish", confidence="high"),
        user_id=1,
        report_id=7,
        as_of=date(2026, 8, 7),
    )
    assert p.direction == "bearish"
    assert p.confidence == "high"
    assert p.report_id == 7
    assert p.status == "pending"
    # 20 交易日 ≈ 28 自然日
    assert p.due_at == date(2026, 8, 7) + timedelta(days=28)
    assert p.factor_snapshot is not None
    assert p.factor_snapshot["composite_score"] == 6.5  # type: ignore[index]


def _bars(closes: list[float], start_date: str = "2026-01-01") -> list[dict[str, float | str]]:
    from datetime import timedelta as td

    day = datetime.strptime(start_date, "%Y-%m-%d").date()
    out = []
    for i, c in enumerate(closes):
        out.append(
            {
                "date": (day + td(days=i)).isoformat(),
                "close": c,
            }
        )
    return out


def test_score_bullish_hit() -> None:
    p = Prediction(
        user_id=1,
        symbol="600519",
        name="贵州茅台",
        direction="bullish",
        confidence="medium",
        horizon_days=20,
        claim="看多",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        due_at=date(2026, 1, 29),
        status="pending",
    )
    _score_one(p, _bars([100.0, 105.0]))
    assert p.status == "scored"
    assert p.outcome == "correct"
    assert p.actual_return_pct == pytest.approx(5.0)


def test_score_bullish_miss() -> None:
    p = Prediction(
        user_id=1,
        symbol="600519",
        name="贵州茅台",
        direction="bullish",
        confidence="high",
        horizon_days=20,
        claim="看多",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        due_at=date(2026, 1, 29),
        status="pending",
    )
    _score_one(p, _bars([100.0, 93.0]))
    assert p.outcome == "incorrect"
    assert p.actual_return_pct == pytest.approx(-7.0)


def test_score_neutral_direction_only_fails_on_big_move() -> None:
    p = Prediction(
        user_id=1,
        symbol="600519",
        name="贵州茅台",
        direction="neutral",
        confidence="low",
        horizon_days=20,
        claim="中性",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        due_at=date(2026, 1, 29),
        status="pending",
    )
    _score_one(p, _bars([100.0, 98.0]))
    assert p.outcome == "neutral"  # 小幅波动不判错

    p2 = Prediction(
        user_id=1,
        symbol="600519",
        name="贵州茅台",
        direction="neutral",
        confidence="low",
        horizon_days=20,
        claim="中性",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        due_at=date(2026, 1, 29),
        status="pending",
    )
    _score_one(p2, _bars([100.0, 88.0]))
    assert p2.outcome == "incorrect"  # 大幅波动说明方向判断失败


def test_score_skips_when_not_due_or_no_bars() -> None:
    not_due = Prediction(
        user_id=1,
        symbol="600519",
        name="贵州茅台",
        direction="bullish",
        confidence="medium",
        horizon_days=20,
        claim="",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        due_at=date(2026, 12, 31),
        status="pending",
    )
    _score_one(not_due, _bars([100.0, 105.0]))
    assert not_due.status == "pending"

    no_bars = Prediction(
        user_id=1,
        symbol="600519",
        name="贵州茅台",
        direction="bullish",
        confidence="medium",
        horizon_days=20,
        claim="",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        due_at=date(2026, 1, 29),
        status="pending",
    )
    _score_one(no_bars, _bars([100.0]))
    assert no_bars.status == "skipped"


def test_prediction_stats_honest_denominator(db_session) -> None:
    for outcome in ("correct", "correct", "incorrect", "neutral"):
        db_session.add(
            Prediction(
                user_id=1,
                symbol="600519",
                name="贵州茅台",
                direction="bullish",
                confidence="medium",
                horizon_days=20,
                claim="",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                due_at=date(2026, 1, 29),
                status="scored",
                outcome=outcome,  # type: ignore[arg-type]
                actual_return_pct=5.0,
                scored_at=datetime(2026, 2, 1, tzinfo=UTC),
            )
        )
    db_session.commit()
    stats = prediction_stats(db_session, user_id=1)
    assert stats["scored"] == 4
    assert stats["correct"] == 2
    assert stats["incorrect"] == 1
    # neutral 不计入分母：命中率 = 2/3
    assert stats["hit_rate"] == pytest.approx(round(2 / 3, 4))
    assert stats["by_confidence"]["medium"]["correct"] == 2
