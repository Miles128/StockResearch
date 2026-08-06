"""预测日记（Phase 12a）— 研报结论留存、到期评分、准确率统计。

北极星一（预测准确率）的地基：每个预测被记录 → 到期评分 → 校准与归因学习
（12b/12d 依赖本模块数据）。合规纪律：评分含错误预测的诚实展示；"预测准"
的定义是方向判断与概率表述在统计上被事后验证，不是给买卖信号。
"""

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from stockresearch.core.schemas import ResearchReportOut
from stockresearch.db.models import Prediction

logger = logging.getLogger(__name__)

# 默认预测 horizon（交易日）；评分阈值：方向命中要求 |收益| >= 该值。
DEFAULT_HORIZON_DAYS = 20
# 方向命中阈值（%）：|收益| 超过此值才算方向被验证。
HIT_THRESHOLD_PCT = 2.0
# 中性预测的容差（%）：|收益| 超过此值视为方向判断失败。
NEUTRAL_TOLERANCE_PCT = 3.0


def extract_prediction(
    report: ResearchReportOut,
    *,
    user_id: int,
    report_id: int | None = None,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    as_of: date | None = None,
) -> Prediction:
    """从研报事实层提取预测记录（direction/confidence 不二次推断）。

    due_at 用自然日近似 horizon 交易日（20 交易日 ≈ 28 自然日）。
    """
    created = as_of or date.today()
    return Prediction(
        user_id=user_id,
        symbol=report.symbol,
        name=report.name,
        direction=report.bias,
        confidence=report.composite_confidence,
        horizon_days=horizon_days,
        claim=report.summary[:500],
        report_id=report_id,
        factor_snapshot={
            "composite_score": report.composite_score,
            "analysis_depth": report.analysis_depth,
        },
        created_at=datetime.now(UTC),
        due_at=created + timedelta(days=max(horizon_days, 1) * 7 // 5),
        status="pending",
    )


def record_prediction_for_report(
    db: Session,
    user_id: int,
    report: ResearchReportOut,
    *,
    report_id: int | None = None,
) -> Prediction | None:
    """研报持久化时自动留存预测记录（幂等：同一报告不重复记录）。"""
    if not report or not report.symbol:
        return None
    if report_id is not None:
        existing = (
            db.query(Prediction)
            .filter(Prediction.report_id == report_id, Prediction.user_id == user_id)
            .first()
        )
        if existing is not None:
            return existing
    prediction = extract_prediction(report, user_id=user_id, report_id=report_id)
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    logger.info(
        "prediction recorded: %s %s dir=%s conf=%s due=%s",
        prediction.symbol,
        prediction.name,
        prediction.direction,
        prediction.confidence,
        prediction.due_at,
    )
    return prediction


def _score_one(prediction: Prediction, bars: list[dict[str, float | str]]) -> None:
    """按 qfq 日线给单条预测评分（PIT：只用预测之后的日线）。"""
    if prediction.status != "pending" or prediction.due_at > date.today():
        return
    closes = [float(b["close"]) for b in bars if b.get("date") is not None]
    if len(closes) < 2:
        prediction.status = "skipped"
        return
    # 起始价 = 预测日当天的收盘（最近一根 <= created_at 的 bar）
    start_date = prediction.created_at.date()
    start_bar = next((b for b in bars if str(b.get("date", ""))[:10] <= str(start_date)), None)
    start_close = float(start_bar["close"]) if start_bar is not None else closes[0]
    end_close = closes[-1]
    if start_close <= 0:
        prediction.status = "skipped"
        return
    ret_pct = (end_close - start_close) / start_close * 100.0
    prediction.actual_return_pct = round(ret_pct, 4)

    direction = prediction.direction
    if direction == "bullish":
        outcome = (
            "correct"
            if ret_pct >= HIT_THRESHOLD_PCT
            else ("incorrect" if ret_pct <= -HIT_THRESHOLD_PCT else "neutral")
        )
    elif direction == "bearish":
        outcome = (
            "correct"
            if ret_pct <= -HIT_THRESHOLD_PCT
            else ("incorrect" if ret_pct >= HIT_THRESHOLD_PCT else "neutral")
        )
    else:  # neutral：方向不明，只有大幅波动才算判断失败
        outcome = "incorrect" if abs(ret_pct) > NEUTRAL_TOLERANCE_PCT else "neutral"

    prediction.outcome = outcome
    prediction.status = "scored"
    prediction.scored_at = datetime.now(UTC)


async def score_due_predictions(db_factory: Callable[[], Session]) -> int:
    """到期预测评分（worker 每日调用；日线刷新后执行）。返回评分条数。"""
    from stockresearch.services.daily_bars import get_bars_for_symbol

    db = db_factory()
    scored = 0
    try:
        due = (
            db.query(Prediction)
            .filter(Prediction.status == "pending", Prediction.due_at <= date.today())
            .limit(200)
            .all()
        )
        for prediction in due:
            try:
                bars = await get_bars_for_symbol(
                    prediction.symbol, days=prediction.horizon_days + 60
                )
                _score_one(prediction, bars)
                scored += 1
            except Exception as exc:
                logger.warning("prediction scoring failed for %s: %s", prediction.symbol, exc)
        if scored:
            db.commit()
            logger.info("scored %d predictions", scored)
    finally:
        db.close()
    return scored


def prediction_stats(db: Session, user_id: int) -> dict[str, object]:
    """准确率统计（含错误与中性，诚实口径）。

    命中率 = correct / (correct + incorrect)；neutral 不计入分母。
    """
    rows = (
        db.query(
            Prediction.direction,
            Prediction.confidence,
            Prediction.outcome,
            func.count(Prediction.id),
        )
        .filter(Prediction.user_id == user_id, Prediction.status == "scored")
        .group_by(Prediction.direction, Prediction.confidence, Prediction.outcome)
        .all()
    )
    total_correct = 0
    total_incorrect = 0
    total_neutral = 0
    by_confidence: dict[str, dict[str, int]] = {}
    by_direction: dict[str, dict[str, int]] = {}
    for direction, confidence, outcome, count in rows:
        bucket = by_confidence.setdefault(confidence, {"correct": 0, "incorrect": 0, "neutral": 0})
        d_bucket = by_direction.setdefault(direction, {"correct": 0, "incorrect": 0, "neutral": 0})
        if outcome == "correct":
            total_correct += count
            bucket["correct"] += count
            d_bucket["correct"] += count
        elif outcome == "incorrect":
            total_incorrect += count
            bucket["incorrect"] += count
            d_bucket["incorrect"] += count
        elif outcome == "neutral":
            total_neutral += count
            bucket["neutral"] += count
            d_bucket["neutral"] += count
    denominator = total_correct + total_incorrect
    return {
        "scored": total_correct + total_incorrect + total_neutral,
        "correct": total_correct,
        "incorrect": total_incorrect,
        "neutral": total_neutral,
        "hit_rate": round(total_correct / denominator, 4) if denominator else None,
        "by_confidence": by_confidence,
        "by_direction": by_direction,
    }
