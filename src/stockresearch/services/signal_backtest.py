"""Read-only research-signal verification: forward returns after historical report bias."""

from __future__ import annotations

import logging
from datetime import datetime
from statistics import median

from sqlalchemy.orm import Session

from stockresearch.core.constants import DISCLAIMER
from stockresearch.core.schemas import ReportPostHocHorizon, SignalBacktestHorizon, SignalBacktestOut
from stockresearch.db.models import ResearchReport
from stockresearch.services.daily_bars import get_bars_meta_for_symbol

logger = logging.getLogger(__name__)

_MIN_SAMPLE_FOR_CONFIDENCE = 8


def _parse_date(value: str) -> datetime | None:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(value[:10], fmt)
        except ValueError:
            continue
    return None


def _forward_return_pct(bars: list[dict[str, float | str]], start_idx: int, horizon: int) -> float | None:
    if start_idx < 0 or start_idx >= len(bars):
        return None
    end_idx = start_idx + horizon
    if end_idx >= len(bars):
        return None
    start_close = float(bars[start_idx]["close"])
    end_close = float(bars[end_idx]["close"])
    if start_close <= 0:
        return None
    return (end_close - start_close) / start_close * 100.0


def _factor_tilt(payload: dict[str, object]) -> str | None:
    """Optional tilt from saved numeric factors (momentum / pe / volatility).

    High realized vol suppresses momentum-only bullish tilts so verification
    does not treat noisy spikes as directional signal.
    """
    raw = payload.get("factors")
    if not isinstance(raw, list) or not raw:
        return None
    mom = None
    pe_pct = None
    vol = None
    for item in raw:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", ""))
        if key == "momentum_20d" and isinstance(item.get("value"), (int, float)):
            mom = float(item["value"])
        if key == "pe_percentile" and isinstance(item.get("percentile"), (int, float)):
            pe_pct = float(item["percentile"])
        if key == "volatility_20d" and isinstance(item.get("value"), (int, float)):
            vol = float(item["value"])

    high_vol = vol is not None and vol > 40.0

    if mom is not None and mom >= 5:
        # High-vol + strong momentum still counts; high-vol + mild mom does not.
        if high_vol and mom < 8:
            pass
        else:
            return "bullish"
    if mom is not None and mom <= -5:
        if high_vol and mom > -8:
            pass
        else:
            return "bearish"
    if pe_pct is not None and pe_pct <= 0.3:
        return "bullish"
    if pe_pct is not None and pe_pct >= 0.7:
        return "bearish"
    return None


def _avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _med(values: list[float]) -> float | None:
    return float(median(values)) if values else None


def _build_sample_bias_note(
    *,
    unique_symbols: int,
    total_samples: int,
    bias_count: int,
    tilt_count: int,
    skipped_non_qfq: int,
) -> str:
    parts = [
        "样本来自本机历史研报，存在选择偏差；未计入交易成本与冲击成本；仅使用前复权(qfq)日线。",
        f"覆盖 {unique_symbols} 只标的、{total_samples} 条可验证信号"
        f"（研报偏向 {bias_count} · 因子倾斜 {tilt_count}）。",
    ]
    if skipped_non_qfq:
        parts.append(f"另有 {skipped_non_qfq} 条因无 qfq 日线被跳过。")
    if total_samples > 0 and total_samples < _MIN_SAMPLE_FOR_CONFIDENCE:
        parts.append(f"样本量 < {_MIN_SAMPLE_FOR_CONFIDENCE}，统计仅供粗看，勿过度解读。")
    return "".join(parts)


def _empty_side_bucket() -> dict[str, list[float]]:
    return {"bullish": [], "bearish": []}


async def _load_qfq_bars(
    symbol: str,
    cache: dict[str, list[dict[str, float | str]] | None],
) -> list[dict[str, float | str]] | None:
    if symbol in cache:
        return cache[symbol]
    try:
        meta = await get_bars_meta_for_symbol(symbol, days=180)
        if meta.adjust != "qfq" or not meta.bars:
            cache[symbol] = None
            return None
        cache[symbol] = meta.bars
        return meta.bars
    except Exception:
        logger.warning("qfq bars load failed for signal backtest %s", symbol, exc_info=True)
        cache[symbol] = None
        return None


def _start_idx_for_day(bars: list[dict[str, float | str]], report_day) -> int:
    start_idx = -1
    for i, bar in enumerate(bars):
        bar_dt = _parse_date(str(bar.get("date", "")))
        if bar_dt and bar_dt.date() >= report_day:
            start_idx = i
            break
    return start_idx


async def compute_report_post_hoc(
    db: Session,
    user_id: int,
    report_id: int,
    *,
    horizons: tuple[int, ...] = (5, 10, 20),
) -> list[ReportPostHocHorizon]:
    """Per-report forward returns after creation (research verification, not a strategy)."""
    row = (
        db.query(ResearchReport)
        .filter(ResearchReport.user_id == user_id, ResearchReport.id == report_id)
        .one_or_none()
    )
    if row is None:
        return []
    meta = await get_bars_meta_for_symbol(row.symbol, days=180)
    if meta.adjust != "qfq" or not meta.bars:
        return [
            ReportPostHocHorizon(
                days=h,
                return_pct=None,
                partial=True,
                note=meta.note or "前复权日线不可用",
            )
            for h in horizons
        ]
    start_idx = _start_idx_for_day(meta.bars, row.created_at.date())
    if start_idx < 0:
        return [
            ReportPostHocHorizon(days=h, return_pct=None, partial=True, note="尚无后续交易日")
            for h in horizons
        ]
    out: list[ReportPostHocHorizon] = []
    for h in horizons:
        ret = _forward_return_pct(meta.bars, start_idx, h)
        out.append(
            ReportPostHocHorizon(
                days=h,
                return_pct=round(ret, 2) if ret is not None else None,
                partial=ret is None,
                note=None if ret is not None else "窗口未满",
                bars_adjust="qfq",
                bars_source=meta.source,
            )
        )
    return out


async def compute_signal_backtest(
    db: Session,
    user_id: int,
    *,
    horizons: tuple[int, ...] = (5, 10, 20),
) -> SignalBacktestOut:
    rows = (
        db.query(ResearchReport)
        .filter(ResearchReport.user_id == user_id)
        .order_by(ResearchReport.created_at.asc())
        .all()
    )
    cache: dict[str, list[dict[str, float | str]] | None] = {}

    # Combined (bias preferred, else tilt) — primary display
    bucket: dict[int, dict[str, list[float]]] = {h: _empty_side_bucket() for h in horizons}
    bias_bucket: dict[int, dict[str, list[float]]] = {h: _empty_side_bucket() for h in horizons}
    tilt_bucket: dict[int, dict[str, list[float]]] = {h: _empty_side_bucket() for h in horizons}

    used_symbols: set[str] = set()
    bias_signals = 0
    tilt_signals = 0
    factor_hits = 0
    factor_samples = 0
    skipped_non_qfq = 0
    notes: list[str] = []

    for row in rows:
        payload = row.report_json if isinstance(row.report_json, dict) else {}
        bias = str(payload.get("bias", "neutral"))
        tilt = _factor_tilt(payload)
        primary_source: str | None = None
        primary_signal: str | None = None
        if bias in ("bullish", "bearish"):
            primary_signal = bias
            primary_source = "bias"
        elif tilt in ("bullish", "bearish"):
            primary_signal = tilt
            primary_source = "tilt"
        if primary_signal not in ("bullish", "bearish") or primary_source is None:
            continue

        bars = await _load_qfq_bars(row.symbol, cache)
        if bars is None:
            skipped_non_qfq += 1
            continue
        start_idx = _start_idx_for_day(bars, row.created_at.date())
        if start_idx < 0:
            continue

        counted = False
        for h in horizons:
            ret = _forward_return_pct(bars, start_idx, h)
            if ret is None:
                continue
            bucket[h][primary_signal].append(ret)
            if bias in ("bullish", "bearish"):
                bias_bucket[h][bias].append(ret)
            if tilt in ("bullish", "bearish"):
                tilt_bucket[h][tilt].append(ret)
            if not counted:
                used_symbols.add(row.symbol)
                if primary_source == "bias":
                    bias_signals += 1
                else:
                    tilt_signals += 1
                counted = True
            if primary_source == "tilt":
                factor_samples += 1
                if (tilt == "bullish" and ret > 0) or (tilt == "bearish" and ret < 0):
                    factor_hits += 1

    if skipped_non_qfq:
        notes.append(f"跳过 {skipped_non_qfq} 条无前复权日线的样本")
    if factor_samples > 0:
        rate = round(factor_hits / factor_samples * 100.0, 1)
        notes.append(
            f"因子倾斜样本 {factor_samples}，方向命中率 {rate}%（启发式，非策略回测）"
        )
    if bias_signals and tilt_signals:
        notes.append(
            f"信号来源分层：研报偏向 {bias_signals} 条优先计入合计；因子倾斜另列 {tilt_signals} 条"
        )

    out_horizons: list[SignalBacktestHorizon] = []
    for h in horizons:
        bull = bucket[h]["bullish"]
        bear = bucket[h]["bearish"]
        bull_avg = _avg(bull)
        bear_avg = _avg(bear)
        bull_med = _med(bull)
        bear_med = _med(bear)
        bull_hit = (sum(1 for x in bull if x > 0) / len(bull) * 100) if bull else None
        bear_hit = (sum(1 for x in bear if x < 0) / len(bear) * 100) if bear else None
        spread = (
            round(bull_avg - bear_avg, 2)
            if bull_avg is not None and bear_avg is not None
            else None
        )
        sample_n = len(bull) + len(bear)
        if sample_n > 0 and sample_n < _MIN_SAMPLE_FOR_CONFIDENCE:
            notes.append(f"{h} 日窗口样本仅 {sample_n}，命中率波动大")

        bias_bull = bias_bucket[h]["bullish"]
        bias_bear = bias_bucket[h]["bearish"]
        tilt_bull = tilt_bucket[h]["bullish"]
        tilt_bear = tilt_bucket[h]["bearish"]
        out_horizons.append(
            SignalBacktestHorizon(
                days=h,
                sample_count=sample_n,
                bullish_count=len(bull),
                bearish_count=len(bear),
                bullish_avg_return_pct=round(bull_avg, 2) if bull_avg is not None else None,
                bearish_avg_return_pct=round(bear_avg, 2) if bear_avg is not None else None,
                bullish_median_return_pct=round(bull_med, 2) if bull_med is not None else None,
                bearish_median_return_pct=round(bear_med, 2) if bear_med is not None else None,
                bullish_positive_rate_pct=round(bull_hit, 1) if bull_hit is not None else None,
                bearish_negative_rate_pct=round(bear_hit, 1) if bear_hit is not None else None,
                spread_avg_return_pct=spread,
                bias_bullish_avg_return_pct=round(_avg(bias_bull), 2) if bias_bull else None,
                bias_bearish_avg_return_pct=round(_avg(bias_bear), 2) if bias_bear else None,
                factor_tilt_bullish_avg_return_pct=round(_avg(tilt_bull), 2) if tilt_bull else None,
                factor_tilt_bearish_avg_return_pct=round(_avg(tilt_bear), 2) if tilt_bear else None,
            )
        )

    seen: set[str] = set()
    deduped_notes: list[str] = []
    for note in notes:
        if note in seen:
            continue
        seen.add(note)
        deduped_notes.append(note)

    total_samples = bias_signals + tilt_signals
    return SignalBacktestOut(
        horizons=out_horizons,
        disclaimer=f"研究信号验证仅供参考，不构成投资建议。{DISCLAIMER}",
        label="研究信号验证",
        notes=deduped_notes,
        sample_bias_note=_build_sample_bias_note(
            unique_symbols=len(used_symbols),
            total_samples=total_samples,
            bias_count=bias_signals,
            tilt_count=tilt_signals,
            skipped_non_qfq=skipped_non_qfq,
        ),
        unique_symbols=len(used_symbols),
        bias_sample_count=bias_signals,
        factor_tilt_sample_count=tilt_signals,
    )
