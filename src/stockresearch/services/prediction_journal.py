"""预测日记（Phase 12a）— 研报结论留存、到期评分、准确率统计。

北极星一（预测准确率）的地基：每个预测被记录 → 到期评分 → 校准与归因学习
（12b/12d 依赖本模块数据）。合规纪律：评分含错误预测的诚实展示；"预测准"
的定义是方向判断与概率表述在统计上被事后验证，不是给买卖信号。
"""

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from stockresearch.core.schemas import ResearchReportOut
from stockresearch.db.models import Prediction
from stockresearch.utils.llm import LLMClient

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
    factor_snapshot 存四维得分（Phase 12d 归因学习的数据源；旧记录无则归因跳过）。
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
            "dimensions": {
                key: {"score": dim.score, "confidence": dim.confidence}
                for key, dim in report.dimensions.items()
            },
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
    """研报持久化时自动留存预测记录（幂等：同一报告不重复记录）。

    regime 回填由 enrich_prediction_regime（async）单独执行，失败不阻塞记录。
    """
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
    # 起始价 = 预测日当天的收盘（最近一根 <= created_at 的 bar；
    # bars 升序，从尾往前找第一根不晚于预测日的 bar）
    start_date = prediction.created_at.date()
    start_bar = next(
        (b for b in reversed(bars) if str(b.get("date", ""))[:10] <= str(start_date)), None
    )
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
    from stockresearch.services.daily_bars import get_bars_meta_for_symbol

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
                meta = await get_bars_meta_for_symbol(
                    prediction.symbol, days=prediction.horizon_days + 60
                )
                if meta.adjust != "qfq":
                    # PIT 纪律：非 qfq 日线在分红/送转窗口会跳空失真，跳过本轮评分
                    logger.warning(
                        "prediction scoring skipped for %s: bars adjust=%s",
                        prediction.symbol,
                        meta.adjust,
                    )
                    continue
                _score_one(prediction, meta.bars)
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
        db.query(Prediction)
        .filter(Prediction.user_id == user_id, Prediction.status == "scored")
        .limit(1000)
        .all()
    )
    total_correct = 0
    total_incorrect = 0
    total_neutral = 0
    by_confidence: dict[str, dict[str, int]] = {}
    by_direction: dict[str, dict[str, int]] = {}
    by_symbol: dict[str, dict[str, int]] = {}
    by_regime: dict[str, dict[str, int]] = {}
    symbol_names: dict[str, str] = {}
    for p in rows:
        direction, confidence, outcome, symbol = p.direction, p.confidence, p.outcome, p.symbol
        count = 1
        bucket = by_confidence.setdefault(confidence, {"correct": 0, "incorrect": 0, "neutral": 0})
        d_bucket = by_direction.setdefault(direction, {"correct": 0, "incorrect": 0, "neutral": 0})
        s_bucket = by_symbol.setdefault(symbol, {"correct": 0, "incorrect": 0, "neutral": 0})
        symbol_names.setdefault(symbol, symbol)
        r_bucket: dict[str, int] | None = None
        regime: object = None
        if isinstance(p.factor_snapshot, dict):
            regime = p.factor_snapshot.get("regime")
        if isinstance(regime, str) and regime:
            if regime not in by_regime:
                by_regime[regime] = {"correct": 0, "incorrect": 0, "neutral": 0}
            r_bucket = by_regime[regime]
        for b in (bucket, d_bucket, s_bucket, r_bucket):
            if b is None:
                continue
            if outcome == "correct":
                b["correct"] += count
            elif outcome == "incorrect":
                b["incorrect"] += count
            elif outcome == "neutral":
                b["neutral"] += count
        if outcome == "correct":
            total_correct += count
        elif outcome == "incorrect":
            total_incorrect += count
        elif outcome == "neutral":
            total_neutral += count
    denominator = total_correct + total_incorrect
    by_symbol_out: dict[str, dict[str, object]] = {}
    for symbol, s_bucket in by_symbol.items():
        denom = s_bucket["correct"] + s_bucket["incorrect"]
        by_symbol_out[symbol] = {
            "name": symbol_names[symbol],
            "correct": s_bucket["correct"],
            "incorrect": s_bucket["incorrect"],
            "neutral": s_bucket["neutral"],
            "hit_rate": round(s_bucket["correct"] / denom, 4) if denom else None,
        }
    by_regime_out: dict[str, dict[str, object]] = {}
    for regime, bucket in by_regime.items():
        denom = bucket["correct"] + bucket["incorrect"]
        by_regime_out[regime] = {
            "correct": bucket["correct"],
            "incorrect": bucket["incorrect"],
            "neutral": bucket["neutral"],
            "hit_rate": round(bucket["correct"] / denom, 4) if denom else None,
        }
    return {
        "scored": total_correct + total_incorrect + total_neutral,
        "correct": total_correct,
        "incorrect": total_incorrect,
        "neutral": total_neutral,
        "hit_rate": round(total_correct / denominator, 4) if denominator else None,
        "by_confidence": by_confidence,
        "by_direction": by_direction,
        "by_symbol": by_symbol_out,
        "by_regime": by_regime_out,
    }


def dimension_attribution(db: Session, user_id: int) -> dict[str, object]:
    """维度归因（Phase 12d，观察性）：对已评分且有维度快照的预测，
    按各维度得分分档统计命中率——"该维度高分时的预测是否更准"。

    只做相关性展示，不自动改评分权重（合规与可解释性优先）。
    """
    rows = (
        db.query(Prediction)
        .filter(
            Prediction.user_id == user_id,
            Prediction.status == "scored",
            Prediction.outcome.in_(("correct", "incorrect")),
            Prediction.factor_snapshot.isnot(None),
        )
        .limit(500)
        .all()
    )
    # {dimension: {band: {"correct": n, "incorrect": n}}}
    bands: dict[str, dict[str, dict[str, int]]] = {}
    sample = 0
    for p in rows:
        dims = (p.factor_snapshot or {}).get("dimensions")
        if not isinstance(dims, dict) or not dims:
            continue
        sample += 1
        for key, value in dims.items():
            if not isinstance(value, dict):
                continue
            score = value.get("score")
            if not isinstance(score, (int, float)):
                continue
            band = "high" if score >= 6.5 else "low" if score <= 4.5 else "mid"
            bucket = bands.setdefault(
                key,
                {
                    "high": {"correct": 0, "incorrect": 0},
                    "mid": {"correct": 0, "incorrect": 0},
                    "low": {"correct": 0, "incorrect": 0},
                },
            )[band]
            if p.outcome == "correct":
                bucket["correct"] += 1
            else:
                bucket["incorrect"] += 1
    out: dict[str, object] = {}
    for dim, band_map in bands.items():
        rows_out: dict[str, object] = {}
        for band, counts in band_map.items():
            denom = counts["correct"] + counts["incorrect"]
            rows_out[band] = {
                "correct": counts["correct"],
                "incorrect": counts["incorrect"],
                "hit_rate": round(counts["correct"] / denom, 4) if denom else None,
            }
        out[dim] = rows_out
    return {"dimensions": out, "sample": sample}


async def enrich_prediction_regime_for_report(db: Session, report_id: int) -> None:
    """按研报回填其预测记录的 regime（report_id 维度入口）。"""
    p = db.query(Prediction).filter(Prediction.report_id == report_id).first()
    if p is None:
        return
    try:
        from stockresearch.services.market_regime import current_regime

        snapshot = dict(p.factor_snapshot or {})
        snapshot["regime"] = await current_regime()
        p.factor_snapshot = snapshot
        db.commit()
    except Exception:
        logger.debug("regime enrichment failed for report %s", report_id, exc_info=True)


async def enrich_prediction_regime(db: Session, prediction_id: int) -> None:
    """Phase 12f：预测快照回填当时市场 regime（拉取失败仅丢 regime，不抛错）。"""
    try:
        from stockresearch.services.market_regime import current_regime

        p = db.query(Prediction).filter(Prediction.id == prediction_id).first()
        if p is None:
            return
        snapshot = dict(p.factor_snapshot or {})
        snapshot["regime"] = await current_regime()
        p.factor_snapshot = snapshot
        db.commit()
    except Exception:
        logger.debug("regime enrichment failed for prediction %s", prediction_id, exc_info=True)


async def generate_prediction_review(
    db: Session,
    user_id: int,
    prediction_id: int,
    llm: LLMClient | None = None,
) -> Prediction | None:
    """白话复盘（Phase 12c）：到期评分后用 LLM 生成 2-3 句复盘，结果缓存。

    输入只用已存的预测快照 + 评分结果（PIT 纪律，不重拉事后数据）。
    """
    from stockresearch.core.output_style import output_style_scope
    from stockresearch.utils.llm import get_llm_client

    p = (
        db.query(Prediction)
        .filter(Prediction.id == prediction_id, Prediction.user_id == user_id)
        .first()
    )
    if p is None or p.status != "scored":
        return p
    if p.review_text:
        return p
    client = llm or get_llm_client()
    dims = (
        (p.factor_snapshot or {}).get("dimensions") if isinstance(p.factor_snapshot, dict) else None
    )
    dim_text = ""
    if isinstance(dims, dict):
        dim_text = "；".join(
            f"{k}={v.get('score', '?')}" if isinstance(v, dict) else f"{k}=?"
            for k, v in list(dims.items())[:4]
        )
    direction_cn = {"bullish": "看多", "bearish": "看空", "neutral": "中性"}.get(
        p.direction, p.direction
    )
    outcome_cn = {"correct": "判断正确", "incorrect": "判断错误", "neutral": "方向不明"}.get(
        p.outcome or "", p.outcome or ""
    )
    ret = f"{p.actual_return_pct:+.2f}%" if p.actual_return_pct is not None else "无收益数据"
    system = (
        "你是投资复盘讲解员。基于以下预测快照与评分结果，用 2~3 句白话复盘："
        "①当时判断是什么、置信度如何；②实际结果（收益）如何、对错；"
        "③结合当时的维度得分，给出一个可能的解释和一条可执行的认知教训。"
        "禁止给出买卖建议；语气平实克制；如果数据不足，如实说明。"
    )
    user = (
        f"预测：{p.name}({p.symbol}) {direction_cn}（{p.confidence} 置信），"
        f"horizon {p.horizon_days} 交易日。\n"
        f"当时的四维得分：{dim_text or '未记录'}。\n"
        f"当时结论摘要：{p.claim[:200]}\n"
        f"实际结果：{ret}，{outcome_cn}。"
    )
    with output_style_scope(reading_mode="friendly"):
        text = await client.complete(system, user)
    # 合规：LLM 复盘输出过禁用模式清洗（PRD §9.1）
    from stockresearch.services.neutral_guard import apply_ban_filter

    text = apply_ban_filter(text)
    p.review_text = text.strip()[:800]
    db.commit()
    return p
