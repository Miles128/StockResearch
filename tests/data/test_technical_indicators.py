"""Technical indicator series tests."""

from stockresearch.data.technical_indicators import macd_series, rsi_series


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
