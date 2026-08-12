"""Factor screener — 纯函数/服务单元测试（条件匹配与缺数跳过）。"""

from stockresearch.core.schemas import NumericFactorOut, ScreenCondition
from stockresearch.services.screener import _factor_value, _passes


def _f(key: str, value: float | None = 5.0, percentile: float | None = None) -> NumericFactorOut:
    return NumericFactorOut(key=key, label=key, value=value, percentile=percentile, unit="%")


def test_factor_value_returns_float() -> None:
    assert _factor_value({"momentum_20d": _f("momentum_20d", 5.0)}, "momentum_20d") == 5.0
    assert _factor_value({"momentum_20d": _f("momentum_20d", None)}, "momentum_20d") is None
    assert _factor_value({}, "momentum_20d") is None


def test_factor_value_pe_percentile_uses_percentile_field() -> None:
    # value 为空但 percentile 存在（0.42）→ 42.0
    assert (
        _factor_value(
            {"pe_percentile": _f("pe_percentile", None, percentile=0.42)}, "pe_percentile"
        )
        == 42.0
    )
    # percentile > 1 时直接用原值
    assert (
        _factor_value(
            {"pe_percentile": _f("pe_percentile", None, percentile=42.0)}, "pe_percentile"
        )
        == 42.0
    )


def test_passes_all_operators() -> None:
    factors = {"momentum_20d": _f("momentum_20d", 5.0)}
    assert _passes(factors, [ScreenCondition(key="momentum_20d", op=">", value=0)])
    assert _passes(factors, [ScreenCondition(key="momentum_20d", op=">=", value=5.0)])
    assert _passes(factors, [ScreenCondition(key="momentum_20d", op="<", value=10)])
    assert _passes(factors, [ScreenCondition(key="momentum_20d", op="<=", value=5.0)])
    assert not _passes(factors, [ScreenCondition(key="momentum_20d", op=">", value=5.0)])
    assert not _passes(factors, [ScreenCondition(key="momentum_20d", op="<", value=5.0)])


def test_passes_missing_factor_fails() -> None:
    factors = {"momentum_20d": _f("momentum_20d", None)}
    assert not _passes(factors, [ScreenCondition(key="momentum_20d", op=">", value=0)])


def test_passes_all_conditions_required() -> None:
    factors = {"momentum_20d": _f("momentum_20d", 5.0), "pe_percentile": _f("pe_percentile", 20.0)}
    both = [
        ScreenCondition(key="momentum_20d", op=">", value=0),
        ScreenCondition(key="pe_percentile", op="<", value=30),
    ]
    assert _passes(factors, both)
    assert not _passes(factors, [*both, ScreenCondition(key="volatility_20d", op=">", value=0)])
