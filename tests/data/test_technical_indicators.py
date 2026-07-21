"""Technical indicator series tests."""

from stockresearch.data.technical_indicators import (
    atr_series,
    boll_series,
    kdj_series,
    macd_series,
    rsi_series,
)


def test_rsi_series_has_values_after_warmup() -> None:
    closes = [float(10 + i * 0.1) for i in range(30)]
    rsi = rsi_series(closes)
    assert rsi[14] is not None
    assert 0 <= rsi[-1] <= 100  # type: ignore[operator]


def test_macd_series_aligned_length() -> None:
    closes = [float(100 + i) for i in range(40)]
    macd = macd_series(closes)
    assert len(macd["macd"]) == len(closes)
    assert any(v is not None for v in macd["macd"])


def test_boll_series_bands_order() -> None:
    closes = [float(100 + (i % 5) - 2) for i in range(40)]
    boll = boll_series(closes)
    assert len(boll["mid"]) == len(closes)
    for i, mid in enumerate(boll["mid"]):
        if mid is None:
            continue
        assert boll["upper"][i] is not None and boll["lower"][i] is not None
        assert boll["upper"][i] >= mid >= boll["lower"][i]  # type: ignore[operator]


def test_atr_and_kdj_warmup() -> None:
    highs = [float(101 + i * 0.1) for i in range(30)]
    lows = [float(99 + i * 0.1) for i in range(30)]
    closes = [float(100 + i * 0.1) for i in range(30)]
    atr = atr_series(highs, lows, closes)
    assert atr[14] is not None
    kdj = kdj_series(highs, lows, closes)
    assert kdj["k"][8] is not None
    assert kdj["d"][8] is not None
    assert kdj["j"][8] is not None
