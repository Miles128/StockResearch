"""简单组合优化服务测试 — min_vol / risk_parity / balanced，纯 Python 无 numpy。"""

import pytest

from stockresearch.services.portfolio_optimizer import (
    _aligned_returns,
    _balanced_weights,
    _cov_matrix,
    _min_vol_weights,
    _portfolio_return,
    _portfolio_vol,
    _risk_parity_weights,
    optimize_portfolio,
)


def _series(prices: list[float]) -> list[tuple[str, float]]:
    from datetime import date, timedelta

    start = date(2024, 1, 1)
    return [(str(start + timedelta(days=i)), p) for i, p in enumerate(prices)]


def _rising(n: int = 60, base: float = 10.0, step: float = 0.05) -> list[float]:
    return [base + i * step for i in range(n)]


def _volatile(n: int = 60, base: float = 10.0) -> list[float]:
    out = [base]
    for i in range(1, n):
        out.append(out[-1] * (1.0 + (0.02 if i % 2 else -0.02)))
    return out


def _mild(n: int = 60, base: float = 10.0) -> list[float]:
    out = [base]
    for i in range(1, n):
        out.append(out[-1] * (1.0 + (0.005 if i % 2 else -0.005)))
    return out


def test_aligned_returns_common_dates_only() -> None:
    series = {
        "A": [("2024-01-01", 10.0), ("2024-01-02", 11.0), ("2024-01-03", 12.0)],
        "B": [("2024-01-01", 20.0), ("2024-01-03", 22.0)],
    }
    rets = _aligned_returns(series)
    assert set(rets) == {"A", "B"}
    assert len(rets["A"]) == 1  # 只有 01-01→01-03 一个共同区间


def test_cov_matrix_shape_and_diagonal() -> None:
    returns = {
        "A": [0.01, -0.01, 0.02, 0.0, 0.01],
        "B": [0.005, -0.005, 0.01, 0.0, 0.005],
    }
    cov = _cov_matrix(returns)
    assert cov is not None
    assert len(cov) == 2 and len(cov[0]) == 2
    assert cov[0][0] > 0
    assert cov[1][1] > 0


def test_min_vol_weights_long_only_capped() -> None:
    cov = [
        [0.04, 0.005, 0.005],
        [0.005, 0.16, 0.01],
        [0.005, 0.01, 0.09],
    ]
    w = _min_vol_weights(cov)
    assert abs(sum(w) - 1.0) < 1e-6
    assert all(0.0 <= x <= 0.41 for x in w)
    # 波动最小的 A 应该拿到最多权重
    assert w[0] == max(w)


def test_risk_parity_weights_inverse_vol() -> None:
    # 反波动率：vol 小的票权重更大；受 40% 单票上限约束，权重和为 1
    w = _risk_parity_weights([0.1, 0.2, 0.4])
    assert abs(sum(w) - 1.0) < 1e-6
    assert max(w) <= 0.4 + 1e-9
    assert w[0] >= w[1] - 1e-9 >= w[2]
    assert w[2] < 0.3
    assert all(0.0 <= x <= 0.4 + 1e-9 for x in w)


def test_risk_parity_no_cap_when_balanced() -> None:
    # vol 差异不大时不应触发 40% 上限
    w = _risk_parity_weights([0.25, 0.3, 0.35])
    assert abs(sum(w) - 1.0) < 1e-6
    assert max(w) < 0.4
    assert w[0] > w[1] > w[2]


def test_balanced_weights_drops_negative_return() -> None:
    returns = {
        "A": [0.01, 0.02, 0.01, 0.02, 0.01],
        "B": [-0.01, -0.02, -0.01, -0.02, -0.01],
        "C": [0.005, 0.006, 0.004, 0.005, 0.006],
    }
    vols = [0.05, 0.05, 0.02]
    w, cash = _balanced_weights(returns, vols)
    assert abs(sum(w) + cash - 1.0) < 1e-3
    assert w[1] == 0.0  # 负收益归零
    assert all(0.0 <= x <= 0.4 + 1e-9 for x in w)


def test_balanced_weights_cap_creates_cash() -> None:
    # 单一高夏普标的超过 40% 上限 → 超出部分记为现金
    returns = {
        "A": [0.02] * 10,
        "B": [0.001] * 10,
    }
    vols = [0.05, 0.2]
    w, cash = _balanced_weights(returns, vols)
    assert w[0] == 0.4
    assert cash > 0.3
    assert abs(sum(w) + cash - 1.0) < 1e-3


def test_portfolio_vol_and_return() -> None:
    cov = [[0.04, 0.0], [0.0, 0.16]]
    w = [0.5, 0.5]
    vol = _portfolio_vol(w, cov)
    assert abs(vol - (0.04 * 0.25 + 0.16 * 0.25) ** 0.5) < 1e-9
    returns = {"A": [0.01] * 5, "B": [0.02] * 5}
    ret = _portfolio_return(w, returns)
    assert ret > 0


@pytest.mark.asyncio
async def test_optimize_min_vol(monkeypatch: pytest.MonkeyPatch) -> None:
    from stockresearch.services.daily_bars import BarsMeta

    async def _fake_meta(symbol: str, days: int = 250):
        prices = _rising(base=10.0 + (ord(symbol[-1]) % 5), step=0.05)
        return BarsMeta(
            bars=[{"date": d, "close": p} for d, p in _series(prices)],
            source="warehouse",
            adjust="qfq",
            as_of="2024-03-01",
        )

    monkeypatch.setattr(
        "stockresearch.services.portfolio_optimizer.get_bars_meta_for_symbol",
        _fake_meta,
    )

    out = await optimize_portfolio({"600000": 0.7, "600001": 0.3, "600002": 0.0}, method="min_vol")
    assert out.method == "min_vol"
    assert len(out.rows) == 3
    assert abs(sum(r.optimal_weight for r in out.rows) - 1.0) < 1e-3
    assert all(r.optimal_weight >= 0 for r in out.rows)
    assert out.optimal_vol is not None
    assert out.current_vol is not None
    assert "波动" in out.explanation
    assert not out.partial


@pytest.mark.asyncio
async def test_optimize_risk_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    from stockresearch.services.daily_bars import BarsMeta

    async def _fake_meta(symbol: str, days: int = 250):
        if symbol == "600000":
            prices = _rising(step=0.02)  # 近乎零波动
        elif symbol == "600001":
            prices = _volatile()  # ±2% 交替
        else:
            prices = _mild()  # ±0.5% 交替
        return BarsMeta(
            bars=[{"date": d, "close": p} for d, p in _series(prices)],
            source="warehouse",
            adjust="qfq",
            as_of="2024-03-01",
        )

    monkeypatch.setattr(
        "stockresearch.services.portfolio_optimizer.get_bars_meta_for_symbol",
        _fake_meta,
    )

    out = await optimize_portfolio(
        {"600000": 0.5, "600001": 0.5, "600002": 0.0}, method="risk_parity"
    )
    assert out.method_label == "风险平价"
    row_map = {r.symbol: r.optimal_weight for r in out.rows}
    # 低波动票到 40% 上限；高波动票权重被压低
    assert row_map["600000"] == 0.4
    assert row_map["600001"] < row_map["600002"]
    assert abs(sum(row_map.values()) - 1.0) < 1e-3


@pytest.mark.asyncio
async def test_optimize_balanced(monkeypatch: pytest.MonkeyPatch) -> None:
    from stockresearch.services.daily_bars import BarsMeta

    async def _fake_meta(symbol: str, days: int = 250):
        if symbol == "600000":
            prices = [10.0 * (1.02**i) for i in range(60)]  # 正收益
        else:
            prices = [10.0 * (0.98**i) for i in range(60)]  # 负收益
        return BarsMeta(
            bars=[{"date": d, "close": p} for d, p in _series(prices)],
            source="warehouse",
            adjust="qfq",
            as_of="2024-03-01",
        )

    monkeypatch.setattr(
        "stockresearch.services.portfolio_optimizer.get_bars_meta_for_symbol",
        _fake_meta,
    )

    out = await optimize_portfolio({"600000": 0.5, "600001": 0.5}, method="balanced")
    assert out.method_label == "均衡"
    row_map = {r.symbol: r.optimal_weight for r in out.rows}
    assert row_map["600001"] == 0.0  # 负收益归零
    assert row_map["600000"] == 0.4  # 上限
    assert out.cash_weight > 0.5  # 剩余记为现金


@pytest.mark.asyncio
async def test_optimize_insufficient_universe(monkeypatch: pytest.MonkeyPatch) -> None:
    from stockresearch.services.daily_bars import BarsMeta

    async def _fake_meta(symbol: str, days: int = 250):
        return BarsMeta(
            bars=[{"date": "2024-01-01", "close": 10.0}],
            source="warehouse",
            adjust="qfq",
            as_of="2024-01-01",
        )

    monkeypatch.setattr(
        "stockresearch.services.portfolio_optimizer.get_bars_meta_for_symbol",
        _fake_meta,
    )

    out = await optimize_portfolio({"600000": 0.5, "600001": 0.5})
    assert out.partial
    assert out.rows == []
    assert "至少需要 2 个" in out.explanation
