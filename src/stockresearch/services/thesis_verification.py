"""Phase 12e 假设自动验证 — deep 档 Thesis 到期自动执行，结果回写研报卡。

预测日记（12a）验证"方向判断"；本模块验证"Thesis 主张是否被证伪"。
PIT 纪律：只用验证之后的数据。
"""

import logging
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from stockresearch.core.schemas import ResearchReportOut
from stockresearch.db.models import ThesisVerification

logger = logging.getLogger(__name__)

DEFAULT_THESIS_HORIZON_DAYS = 60
# 主张受挑战阈值（%）：horizon 收益与方向相反且 |收益| >= 该值。
CHALLENGE_THRESHOLD_PCT = 5.0


def _parse_horizon_days(horizon: str) -> int:
    m = re.search(r"(\d+)", horizon)
    if m:
        try:
            return min(max(int(m.group(1)) * 30, 30), 180)
        except ValueError:
            pass
    return DEFAULT_THESIS_HORIZON_DAYS


def record_thesis_for_report(
    db: Session,
    user_id: int,
    report: ResearchReportOut,
    *,
    report_id: int | None = None,
) -> ThesisVerification | None:
    """deep 档研报持久化时自动创建 Thesis 验证计划（幂等）。"""
    if report.deep_analysis is None or report.deep_analysis.thesis is None:
        return None
    thesis = report.deep_analysis.thesis
    if report_id is not None:
        existing = (
            db.query(ThesisVerification).filter(ThesisVerification.report_id == report_id).first()
        )
        if existing is not None:
            return existing
    horizon_days = _parse_horizon_days(thesis.horizon or "")
    row = ThesisVerification(
        user_id=user_id,
        report_id=report_id,
        symbol=report.symbol,
        name=report.name,
        claim=thesis.claim[:500],
        direction=report.bias,
        monitors=list(thesis.monitors),
        invalidate_if=list(thesis.invalidate_if),
        horizon_days=horizon_days,
        due_at=date.today() + timedelta(days=horizon_days),
        status="pending",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("thesis verification scheduled: %s(%s) due=%s", row.name, row.symbol, row.due_at)
    return row


def _verify_one(row: ThesisVerification, bars: list[dict[str, float | str]]) -> None:
    """到期验证：horizon 收益与方向相反且显著 → 主张受挑战；否则未被证伪。"""
    if row.status != "pending" or row.due_at > date.today():
        return
    closes = [float(b["close"]) for b in bars if b.get("date") is not None]
    if len(closes) < 2:
        row.status = "verified"
        row.result_text = "验证窗口数据不足，未判定。"
        row.checked_at = datetime.now(UTC)
        return
    start_date = row.created_at.date()
    start_bar = next((b for b in bars if str(b.get("date", ""))[:10] <= str(start_date)), None)
    start_close = float(start_bar["close"]) if start_bar is not None else closes[0]
    end_close = closes[-1]
    if start_close <= 0:
        row.status = "verified"
        row.result_text = "起始价不可用，未判定。"
        row.checked_at = datetime.now(UTC)
        return
    ret_pct = (end_close - start_close) / start_close * 100.0
    direction = row.direction
    if direction == "bullish":
        challenged = ret_pct <= -CHALLENGE_THRESHOLD_PCT
    elif direction == "bearish":
        challenged = ret_pct >= CHALLENGE_THRESHOLD_PCT
    else:
        challenged = abs(ret_pct) > CHALLENGE_THRESHOLD_PCT * 1.5
    row.result_text = (
        f"主张受挑战：验证窗收益 {ret_pct:+.2f}%，与当时判断方向相反（阈值 ±{CHALLENGE_THRESHOLD_PCT:.0f}%）。"
        if challenged
        else f"未被证伪：验证窗收益 {ret_pct:+.2f}%，与当时判断方向一致或未达挑战阈值。"
    )
    row.status = "verified"
    row.checked_at = datetime.now(UTC)


async def check_due_theses(db_factory: Callable[[], Session]) -> int:
    """到期 Thesis 验证（worker 每日调用）。返回验证条数。"""
    from stockresearch.services.daily_bars import get_bars_for_symbol

    db = db_factory()
    checked = 0
    try:
        due = (
            db.query(ThesisVerification)
            .filter(
                ThesisVerification.status == "pending", ThesisVerification.due_at <= date.today()
            )
            .limit(100)
            .all()
        )
        for row in due:
            try:
                bars = await get_bars_for_symbol(row.symbol, days=row.horizon_days + 60)
                _verify_one(row, bars)
                checked += 1
            except Exception as exc:
                logger.warning("thesis verification failed for %s: %s", row.symbol, exc)
        if checked:
            db.commit()
            logger.info("verified %d theses", checked)
    finally:
        db.close()
    return checked
