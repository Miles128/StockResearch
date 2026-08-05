"""Server-side trendline detection — Python port of web/src/chartTrendlines.ts.

Parameters stay aligned with the frontend implementation (pivot window 3,
tolerance 0.6%, max 4 lines, relevance filter 15%) so Copilot answers
describe exactly what the chart renders (Phase 9b).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

from stockresearch.core.schemas import ChartOverlay, ChartOverlayPoint, ChartOverlaySet

TrendLineKind = Literal["support", "resistance"]


@dataclass(frozen=True)
class Bar:
    date: str
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class Pivot:
    index: int
    price: float


@dataclass(frozen=True)
class TrendLine:
    kind: TrendLineKind
    start_index: int
    end_index: int
    start_price: float
    end_price: float
    slope_per_bar: float
    touches: int


@dataclass(frozen=True)
class TrendLineOptions:
    pivot_window: int = 3
    tolerance_pct: float = 0.006
    max_lines: int = 4
    min_span: int = 5
    max_span: int = 140
    relevance_pct: float = 0.15


@dataclass(frozen=True)
class LevelOptions:
    """水平参考线参数（与前端 chartTrendlines.detectLevels 对齐）。"""

    lookback: int = 120
    tolerance_pct: float = 0.006
    max_levels: int = 2
    relevance_pct: float = 0.15
    min_touches: int = 2


def find_pivots(bars: list[Bar], k: int) -> tuple[list[Pivot], list[Pivot]]:
    highs: list[Pivot] = []
    lows: list[Pivot] = []
    for i in range(k, len(bars) - k):
        is_high = True
        is_low = True
        for j in range(i - k, i + k + 1):
            if bars[j].high > bars[i].high:
                is_high = False
            if bars[j].low < bars[i].low:
                is_low = False
            if not is_high and not is_low:
                break
        if is_high:
            highs.append(Pivot(i, bars[i].high))
        if is_low:
            lows.append(Pivot(i, bars[i].low))
    return highs, lows


def _score_line(line: TrendLine, max_span: int, last_close: float) -> float:
    span = line.end_index - line.start_index
    span_score = min(span, max_span) / max_span
    distance = abs(line.end_price - last_close) / last_close
    return line.touches * 2 + span_score - distance * 10


def _is_duplicate(a: TrendLine, b: TrendLine, tolerance_pct: float) -> bool:
    if a.kind != b.kind:
        return False
    near_start = abs(a.start_price - b.start_price) <= tolerance_pct * 2 * a.start_price
    near_end = abs(a.end_price - b.end_price) <= tolerance_pct * 2 * a.end_price
    return near_start and near_end


def _fit_lines(
    bars: list[Bar],
    pivots: list[Pivot],
    kind: TrendLineKind,
    opts: TrendLineOptions,
) -> list[TrendLine]:
    last = len(bars) - 1
    out: list[TrendLine] = []
    for ai in range(len(pivots)):
        for bi in range(ai + 1, len(pivots)):
            p1, p2 = pivots[ai], pivots[bi]
            span = p2.index - p1.index
            if span < opts.min_span or span > opts.max_span:
                continue
            slope = (p2.price - p1.price) / span

            def value_at(idx: int, _p1: Pivot = p1, _slope: float = slope) -> float:
                # 绑定默认参数：避免闭包延迟捕获循环变量（B023）
                return _p1.price + _slope * (idx - _p1.index)

            valid = True
            for t in range(p1.index, last + 1):
                lv = value_at(t)
                tol = opts.tolerance_pct * lv
                if kind == "support":
                    if bars[t].low < lv - tol:
                        valid = False
                        break
                elif bars[t].high > lv + tol:
                    valid = False
                    break
            if not valid:
                continue

            touches = 0
            for p in pivots:
                if p.index < p1.index:
                    continue
                lv = value_at(p.index)
                if abs(p.price - lv) <= opts.tolerance_pct * lv:
                    touches += 1
            if touches < 2:
                continue

            out.append(
                TrendLine(
                    kind=kind,
                    start_index=p1.index,
                    end_index=last,
                    start_price=p1.price,
                    end_price=value_at(last),
                    slope_per_bar=slope,
                    touches=touches,
                )
            )
    return out


def detect_trend_lines(
    bars: list[Bar],
    options: TrendLineOptions | None = None,
) -> list[TrendLine]:
    opts = options or TrendLineOptions()
    if len(bars) < opts.min_span + 2 * opts.pivot_window + 2:
        return []

    last_close = bars[-1].close

    def relevant(line: TrendLine) -> bool:
        return abs(line.end_price - last_close) / last_close <= opts.relevance_pct

    highs, lows = find_pivots(bars, opts.pivot_window)
    supports = [line for line in _fit_lines(bars, lows, "support", opts) if relevant(line)]
    resistances = [line for line in _fit_lines(bars, highs, "resistance", opts) if relevant(line)]

    def pick(lines: list[TrendLine], cap: int) -> list[TrendLine]:
        ordered = sorted(
            lines,
            key=lambda line: _score_line(line, opts.max_span, last_close),
            reverse=True,
        )
        kept: list[TrendLine] = []
        for line in ordered:
            if len(kept) >= cap:
                break
            if any(_is_duplicate(k, line, opts.tolerance_pct) for k in kept):
                continue
            kept.append(line)
        return kept

    half = (opts.max_lines + 1) // 2
    return (pick(supports, half) + pick(resistances, half))[: opts.max_lines]


def detect_levels(
    bars: list[Bar],
    options: LevelOptions | None = None,
) -> list[tuple[float, Literal["support", "resistance"], int]]:
    """水平参考线：近期窗口内显著高低点（价格档位），按触碰次数评分。

    返回 [(price, side, touches)]，按触碰次数降序；支撑/压力各自独立分桶，
    避免相邻价位的高低点互相合并。
    """
    opts = options or LevelOptions()
    window = bars[-opts.lookback :]
    if len(window) < 10:
        return []

    last_close = bars[-1].close

    def bucket_levels(
        pivots: list[Pivot],
    ) -> dict[float, list[float]]:
        buckets: dict[float, list[float]] = {}

        def bucket_of(price: float) -> float:
            tol = opts.tolerance_pct * price
            for key in buckets:
                if abs(key - price) <= tol:
                    return key
            return price

        for pivot in pivots:
            key = bucket_of(pivot.price)
            buckets.setdefault(key, []).append(pivot.price)
        return buckets

    k = 3
    highs, lows = find_pivots(window, k)
    out: list[tuple[float, Literal["support", "resistance"], int]] = []
    for side, buckets in (
        ("support", bucket_levels(lows)),
        ("resistance", bucket_levels(highs)),
    ):
        for prices in buckets.values():
            touches = len(prices)
            if touches < opts.min_touches:
                continue
            # 档位价 = 触碰点均值
            level_price = sum(prices) / len(prices)
            if abs(level_price - last_close) / last_close > opts.relevance_pct:
                continue
            out.append((round(level_price, 4), cast(TrendLineKind, side), touches))

    out.sort(key=lambda x: -x[2])
    return out[: opts.max_levels]


def bars_from_kline(raw: dict[str, Any]) -> list[Bar]:
    bars: list[Bar] = []
    for item in raw.get("bars") or []:
        if not isinstance(item, dict):
            continue
        try:
            bars.append(
                Bar(
                    date=str(item["date"]),
                    high=float(item["high"]),
                    low=float(item["low"]),
                    close=float(item["close"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return bars


def _overlay_rationale(line: TrendLine, bars: list[Bar]) -> str:
    side_text = "支撑线" if line.kind == "support" else "压力线"
    anchor = "低点" if line.kind == "support" else "高点"
    last_close = bars[-1].close
    relation = "上方" if line.end_price <= last_close else "下方"
    return (
        f"{side_text}：连接 {bars[line.start_index].date} 与临近末端的{anchor}，"
        f"共 {line.touches} 次触碰；延伸至最新一根K线约 {line.end_price:.2f}，"
        f"位于最新收盘价 {last_close:.2f} 的{relation}。仅为图形描述，不构成交易建议。"
    )


def _level_rationale(
    price: float, side: Literal["support", "resistance"], touches: int, bars: list[Bar]
) -> str:
    side_text = "支撑位" if side == "support" else "压力位"
    last_close = bars[-1].close
    relation = "下方" if price <= last_close else "上方"
    return (
        f"水平{side_text}：近期多次在约 {price:.2f} 附近企稳/受阻（{touches} 次触碰），"
        f"位于最新收盘价 {last_close:.2f} 的{relation}。仅为图形描述，不构成交易建议。"
    )


def build_overlay_set(symbol: str, bars: list[Bar]) -> ChartOverlaySet:
    lines = detect_trend_lines(bars)
    overlays: list[ChartOverlay] = []
    if lines:
        scores = [_score_line(line, TrendLineOptions().max_span, bars[-1].close) for line in lines]
        top = max(scores)
        floor = min(scores)
        span = top - floor
        for line, score in zip(lines, scores, strict=True):
            strength = 1.0 if span <= 0 else max(0.0, min(1.0, (score - floor) / span))
            overlays.append(
                ChartOverlay(
                    id=f"trend-{line.kind}-{line.start_index}-{line.end_index}",
                    kind="trend",
                    a=ChartOverlayPoint(
                        time=bars[line.start_index].date, price=round(line.start_price, 4)
                    ),
                    b=ChartOverlayPoint(
                        time=bars[line.end_index].date, price=round(line.end_price, 4)
                    ),
                    side=line.kind,
                    strength=round(strength, 2),
                    touches=line.touches,
                    source="ai",
                    rationale=_overlay_rationale(line, bars),
                )
            )
    # 水平参考线（Phase 9a）：与趋势线同层展示
    for price, side, touches in detect_levels(bars):
        overlays.append(
            ChartOverlay(
                id=f"level-{side}-{price}",
                kind="level",
                price=price,
                side=side,
                strength=round(min(touches / 4, 1.0), 2),
                touches=touches,
                source="ai",
                rationale=_level_rationale(price, side, touches, bars),
            )
        )
    return ChartOverlaySet(
        symbol=symbol,
        generatedAt=datetime.now(UTC).isoformat(),
        overlays=overlays,
    )


async def compute_chart_overlays(symbol: str, days: int = 250) -> ChartOverlaySet:
    """Fetch daily bars and compute AI trendline overlays for one symbol."""
    from stockresearch.data.providers.market.technical import TechnicalDataProvider

    raw = await TechnicalDataProvider().get_kline_chart(symbol, days)
    return build_overlay_set(symbol, bars_from_kline(raw))
