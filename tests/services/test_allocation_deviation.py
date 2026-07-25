"""Allocation deviation helpers (display only)."""

from types import SimpleNamespace

from stockresearch.services.allocation_deviation import (
    build_allocation_deviation,
    normalize_targets,
    sector_weights,
)


def _h(sector: str, cost: float, qty: int) -> SimpleNamespace:
    return SimpleNamespace(sector=sector, cost_price=cost, quantity=qty)


def test_sector_weights_and_deviation() -> None:
    holdings = [_h("白酒", 100, 10), _h("新能源", 50, 10)]  # 1000 vs 500
    weights = sector_weights(holdings)  # type: ignore[arg-type]
    assert weights["白酒"] == 0.6667
    assert weights["新能源"] == 0.3333

    out = build_allocation_deviation(
        holdings,  # type: ignore[arg-type]
        {"白酒": 50, "新能源": 50},
    )
    assert out.targets["白酒"] == 0.5
    row = next(r for r in out.rows if r.sector == "白酒")
    assert row.delta > 0


def test_normalize_targets_fractions() -> None:
    assert normalize_targets({"a": 0.6, "b": 0.4})["a"] == 0.6
