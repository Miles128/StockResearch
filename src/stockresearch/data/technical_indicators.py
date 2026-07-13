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


def boll_series(
    closes: list[float],
    window: int = 20,
    num_std: float = 2.0,
) -> dict[str, list[float | None]]:
    """Bollinger bands: mid = MA, upper/lower = mid ± num_std * stdev."""
    n = len(closes)
    mid: list[float | None] = [None] * n
    upper: list[float | None] = [None] * n
    lower: list[float | None] = [None] * n
    if window < 2 or n < window:
        return {"mid": mid, "upper": upper, "lower": lower}
    for i in range(window - 1, n):
        segment = closes[i + 1 - window : i + 1]
        mean = sum(segment) / window
        var = sum((x - mean) ** 2 for x in segment) / window
        std = var**0.5
        mid[i] = round(mean, 4)
        upper[i] = round(mean + num_std * std, 4)
        lower[i] = round(mean - num_std * std, 4)
    return {"mid": mid, "upper": upper, "lower": lower}


def atr_series(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> list[float | None]:
    """Average True Range (Wilder smoothing)."""
    n = len(closes)
    out: list[float | None] = [None] * n
    if n < 2 or len(highs) != n or len(lows) != n or period < 1:
        return out
    trs: list[float] = [0.0] * n
    trs[0] = highs[0] - lows[0]
    for i in range(1, n):
        trs[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
    if n <= period:
        return out
    atr = sum(trs[1 : period + 1]) / period
    out[period] = round(atr, 4)
    for i in range(period + 1, n):
        atr = (atr * (period - 1) + trs[i]) / period
        out[i] = round(atr, 4)
    return out


def kdj_series(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    n: int = 9,
    m1: int = 3,
    m2: int = 3,
) -> dict[str, list[float | None]]:
    """KDJ (RSV → K → D → J) with classic A-share defaults 9/3/3."""
    length = len(closes)
    empty: list[float | None] = [None] * length
    if length < n or len(highs) != length or len(lows) != length:
        return {"k": empty[:], "d": empty[:], "j": empty[:]}
    k_line: list[float | None] = [None] * length
    d_line: list[float | None] = [None] * length
    j_line: list[float | None] = [None] * length
    k_prev = 50.0
    d_prev = 50.0
    for i in range(n - 1, length):
        window_high = max(highs[i + 1 - n : i + 1])
        window_low = min(lows[i + 1 - n : i + 1])
        denom = window_high - window_low
        rsv = 50.0 if denom <= 0 else (closes[i] - window_low) / denom * 100.0
        k_prev = (rsv + (m1 - 1) * k_prev) / m1
        d_prev = (k_prev + (m2 - 1) * d_prev) / m2
        j_val = 3 * k_prev - 2 * d_prev
        k_line[i] = round(k_prev, 2)
        d_line[i] = round(d_prev, 2)
        j_line[i] = round(j_val, 2)
    return {"k": k_line, "d": d_line, "j": j_line}
