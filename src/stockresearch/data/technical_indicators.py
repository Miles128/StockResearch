"""OHLCV indicator series for chart API."""

from __future__ import annotations


def _ema_series(values: list[float], period: int) -> list[float | None]:
    if not values:
        return []
    k = 2 / (period + 1)
    out: list[float | None] = [None] * len(values)
    ema = values[0]
    out[0] = ema
    for i in range(1, len(values)):
        ema = values[i] * k + ema * (1 - k)
        out[i] = round(ema, 4)
    return out


def ma_series(closes: list[float], window: int) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    for i in range(len(closes)):
        if i + 1 < window:
            continue
        segment = closes[i + 1 - window : i + 1]
        out[i] = round(sum(segment) / window, 4)
    return out


def rsi_series(closes: list[float], period: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    if len(closes) < period + 1:
        return out
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    idx = period
    rs = avg_gain / avg_loss if avg_loss else 100.0
    out[idx] = round(100 - (100 / (1 + rs)), 2)
    for i in range(period + 1, len(closes)):
        gain = gains[i - 1]
        loss = losses[i - 1]
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        rs = avg_gain / avg_loss if avg_loss else 100.0
        out[i] = round(100 - (100 / (1 + rs)), 2)
    return out


def macd_series(closes: list[float]) -> dict[str, list[float | None]]:
    n = len(closes)
    empty: list[float | None] = [None] * n
    if n < 2:
        return {"macd": empty, "signal": empty, "histogram": empty}
    ema12 = _ema_series(closes, 12)
    ema26 = _ema_series(closes, 26)
    macd_line: list[float | None] = [None] * n
    macd_values: list[float] = []
    macd_indices: list[int] = []
    for i in range(n):
        fast = ema12[i]
        slow = ema26[i]
        if fast is None or slow is None:
            continue
        val = round(fast - slow, 4)
        macd_line[i] = val
        macd_values.append(val)
        macd_indices.append(i)
    signal_line: list[float | None] = [None] * n
    if macd_values:
        signal_ema = _ema_series(macd_values, 9)
        for j, idx in enumerate(macd_indices):
            signal_line[idx] = signal_ema[j]
    histogram: list[float | None] = [None] * n
    for i in range(n):
        macd_value = macd_line[i]
        signal_value = signal_line[i]
        if macd_value is None or signal_value is None:
            continue
        histogram[i] = round(macd_value - signal_value, 4)
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}
