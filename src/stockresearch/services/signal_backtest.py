"""Read-only research-signal verification: forward returns after historical report bias."""

from datetime import datetime

from sqlalchemy.orm import Session

from stockresearch.core.constants import DISCLAIMER
from stockresearch.core.schemas import SignalBacktestHorizon, SignalBacktestOut
from stockresearch.data.providers.market import TechnicalDataProvider
from stockresearch.db.models import ResearchReport
from stockresearch.services.daily_bars import get_bars_for_symbol


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
    """Optional tilt from saved numeric factors (momentum / pe percentile)."""
    raw = payload.get("factors")
    if not isinstance(raw, list) or not raw:
        return None
    mom = None
    pe_pct = None
    for item in raw:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", ""))
        if key == "momentum_20d" and isinstance(item.get("value"), (int, float)):
            mom = float(item["value"])
        if key == "pe_percentile" and isinstance(item.get("percentile"), (int, float)):
            pe_pct = float(item["percentile"])
    if mom is not None and mom >= 5:
        return "bullish"
    if mom is not None and mom <= -5:
        return "bearish"
    if pe_pct is not None and pe_pct <= 0.3:
        return "bullish"
    if pe_pct is not None and pe_pct >= 0.7:
        return "bearish"
    return None


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
    provider = TechnicalDataProvider()
    cache: dict[str, list[dict[str, float | str]]] = {}

    bucket: dict[int, dict[str, list[float]]] = {
        h: {"bullish": [], "bearish": []} for h in horizons
    }
    factor_notes: list[str] = []
    factor_hits = 0
    factor_samples = 0

    for row in rows:
        payload = row.report_json if isinstance(row.report_json, dict) else {}
        bias = str(payload.get("bias", "neutral"))
        tilt = _factor_tilt(payload)
        signal = bias if bias in ("bullish", "bearish") else tilt
        if signal not in ("bullish", "bearish"):
            continue
        if row.symbol not in cache:
            try:
                cache[row.symbol] = await get_bars_for_symbol(row.symbol, days=180)
            except Exception:
                cache[row.symbol] = await provider.get_kline_bars(row.symbol, days=180)
        bars = cache[row.symbol]
        if not bars:
            continue
        report_day = row.created_at.date()
        start_idx = -1
        for i, bar in enumerate(bars):
            bar_dt = _parse_date(str(bar.get("date", "")))
            if bar_dt and bar_dt.date() >= report_day:
                start_idx = i
                break
        if start_idx < 0:
            continue
        for h in horizons:
            ret = _forward_return_pct(bars, start_idx, h)
            if ret is not None:
                bucket[h][signal].append(ret)
                if tilt is not None:
                    factor_samples += 1
                    if (tilt == "bullish" and ret > 0) or (tilt == "bearish" and ret < 0):
                        factor_hits += 1

    if factor_samples > 0:
        rate = round(factor_hits / factor_samples * 100.0, 1)
        factor_notes.append(f"因子倾斜样本 {factor_samples}，方向命中率 {rate}%（启发式，非策略回测）")

    out_horizons: list[SignalBacktestHorizon] = []
    for h in horizons:
        bull = bucket[h]["bullish"]
        bear = bucket[h]["bearish"]
        bull_avg = sum(bull) / len(bull) if bull else None
        bear_avg = sum(bear) / len(bear) if bear else None
        bull_hit = (sum(1 for x in bull if x > 0) / len(bull) * 100) if bull else None
        bear_hit = (sum(1 for x in bear if x < 0) / len(bear) * 100) if bear else None
        out_horizons.append(
            SignalBacktestHorizon(
                days=h,
                sample_count=len(bull) + len(bear),
                bullish_count=len(bull),
                bearish_count=len(bear),
                bullish_avg_return_pct=round(bull_avg, 2) if bull_avg is not None else None,
                bearish_avg_return_pct=round(bear_avg, 2) if bear_avg is not None else None,
                bullish_positive_rate_pct=round(bull_hit, 1) if bull_hit is not None else None,
                bearish_negative_rate_pct=round(bear_hit, 1) if bear_hit is not None else None,
            )
        )

    return SignalBacktestOut(
        horizons=out_horizons,
        disclaimer=f"研究信号验证仅供参考，不构成投资建议。{DISCLAIMER}",
        label="研究信号验证",
        notes=factor_notes,
    )
