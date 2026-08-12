"""Phase 12a 预测日记 — 提取 / 评分 / 统计单元测试。"""

from datetime import UTC, date, datetime, timedelta

import pytest

from stockresearch.core.schemas import ResearchReportOut
from stockresearch.db.models import Prediction
from stockresearch.services.prediction_journal import (
    _score_one,
    dimension_attribution,
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


def test_score_start_bar_is_nearest_before_created_at() -> None:
    """回归：bars 窗口含预测日前数据时，起始价须取「最近一根 ≤ created_at」，
    而非窗口最早一根（否则收益区间混入预测前走势）。"""
    p = Prediction(
        user_id=1,
        symbol="600519",
        name="贵州茅台",
        direction="bullish",
        confidence="medium",
        horizon_days=20,
        claim="看多",
        created_at=datetime(2026, 3, 2, tzinfo=UTC),  # 预测日
        due_at=date(2026, 3, 30),
        status="pending",
    )
    # 窗口从 2026-01-01 起：预测日前 50→100（上涨），预测日后 100→95（下跌）
    bars = _bars(
        [50.0, 60.0, 70.0, 80.0, 90.0, 100.0, 95.0, 95.0, 95.0, 95.0],
        start_date="2026-02-25",
    )
    _score_one(p, bars)
    assert p.status == "scored"
    # 起始价 = 预测日 03-02 附近的 100，而非窗口最早的 50
    assert p.actual_return_pct == pytest.approx(-5.0)
    assert p.outcome == "incorrect"


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


def test_prediction_stats_honest_denominator(db_session) -> None:  # noqa: ANN001
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
    assert stats["by_symbol"]["600519"]["hit_rate"] == pytest.approx(round(2 / 3, 4))


def test_extract_prediction_snapshots_dimension_scores() -> None:
    from stockresearch.core.schemas import DimensionResult

    report = _report(bias="bullish", confidence="high")
    report.dimensions = {
        "fundamental": DimensionResult(
            agent="fundamental",
            score=7.5,
            confidence="high",
            highlights=[],
            risks=[],
            data_sources=[],
        ),
        "technical": DimensionResult(
            agent="technical",
            score=4.0,
            confidence="low",
            highlights=[],
            risks=[],
            data_sources=[],
        ),
    }
    p = extract_prediction(report, user_id=1, as_of=date(2026, 8, 7))
    dims = (p.factor_snapshot or {}).get("dimensions")
    assert dims is not None
    assert dims["fundamental"]["score"] == 7.5  # type: ignore[index]
    assert dims["technical"]["confidence"] == "low"  # type: ignore[index]


def test_dimension_attribution_buckets_by_score(db_session) -> None:  # noqa: ANN001

    snapshots = [
        # 基本面高分 + 方向正确
        {
            "dimensions": {
                "fundamental": {"score": 8.0, "confidence": "high"},
                "technical": {"score": 5.0, "confidence": "medium"},
            }
        },
        # 基本面高分 + 方向错误
        {
            "dimensions": {
                "fundamental": {"score": 7.0, "confidence": "high"},
                "technical": {"score": 5.0, "confidence": "medium"},
            }
        },
        # 技术面低分 + 方向正确
        {
            "dimensions": {
                "fundamental": {"score": 4.0, "confidence": "low"},
                "technical": {"score": 3.5, "confidence": "low"},
            }
        },
    ]
    for i, snap in enumerate(snapshots):
        db_session.add(
            Prediction(
                user_id=1,
                symbol=f"60051{i}",
                name=f"标的{i}",
                direction="bullish",
                confidence="medium",
                horizon_days=20,
                claim="",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                due_at=date(2026, 1, 29),
                status="scored",
                outcome="correct" if i != 1 else "incorrect",  # type: ignore[arg-type]
                actual_return_pct=5.0 if i != 1 else -5.0,
                factor_snapshot=snap,
                scored_at=datetime(2026, 2, 1, tzinfo=UTC),
            )
        )
    db_session.commit()
    attr = dimension_attribution(db_session, user_id=1)
    assert attr["sample"] == 3
    fund = attr["dimensions"]["fundamental"]
    # 高分档：2 条（1 对 1 错）→ 50%；低分档：1 条 → 100%
    assert fund["high"]["hit_rate"] == pytest.approx(0.5)
    assert fund["low"]["hit_rate"] == pytest.approx(1.0)
    # 无维度快照的记录不进入归因
    assert attr["dimensions"].get("nonexistent") is None
