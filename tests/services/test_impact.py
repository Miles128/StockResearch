"""Phase 10 L1 Impact — pure helper + mocked compute_impact tests (no network)."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from stockresearch.core.schemas import EventStudyEventOut, ImpactOut, ImpactPeakDayOut
from stockresearch.services.daily_bars import BarsMeta
from stockresearch.services.impact import (
    _attach_peaks_from_event_study,
    _attach_peaks_from_events,
    _daily_rets,
    _decompose_window,
    _normalize_event_for_peak,
    _ols_beta,
    _peer_ew_returns,
    _top_idio_peak_days,
    attach_impact_events,
    compute_impact,
)


def test_ols_beta_perfect_line() -> None:
    x = [0.01, 0.02, -0.01, 0.0, 0.03]
    y = [2 * v for v in x]
    beta, r2 = _ols_beta(y, x)
    assert abs(beta - 2.0) < 1e-9
    assert r2 > 0.99


def test_ols_beta_constant_x_returns_unit_beta() -> None:
    # var_x ~ 0 → helper returns (1.0, 0.0) instead of dividing by zero.
    beta, r2 = _ols_beta([0.01, 0.02, 0.03], [0.005, 0.005, 0.005])
    assert beta == 1.0
    assert r2 == 0.0


def test_ols_beta_too_few_points_returns_unit() -> None:
    beta, r2 = _ols_beta([0.01], [0.01])
    assert beta == 1.0
    assert r2 == 0.0


def test_decompose_window_sums() -> None:
    # stock 0.02+0.01-0.01 = 0.02 → 2.0%
    # market 0.01+0.01+0.0 = 0.02 → 2.0%; contrib = beta(1.0)*2.0 = 2.0
    # industry 0.005+0.0+0.0 = 0.005 → 0.5%
    # idio = 2.0 - 2.0 - 0.5 = -0.5
    stock = [0.02, 0.01, -0.01]
    mkt = [0.01, 0.01, 0.0]
    ind = [0.005, 0.0, 0.0]
    out = _decompose_window(stock, mkt, ind, beta=1.0)
    assert out["stock_return_pct"] == 2.0
    assert out["market_contrib_pct"] == 2.0
    assert out["industry_contrib_pct"] == 0.5
    assert out["idio_return_pct"] == -0.5


def test_decompose_window_without_industry() -> None:
    # No industry proxy → industry_contrib = 0, idio = stock - market only.
    stock = [0.03, -0.01]
    mkt = [0.01, 0.01]
    out = _decompose_window(stock, mkt, None, beta=2.0)
    # stock_sum = 0.02 * 100 = 2.0; mkt_sum = 0.02 * 100 = 2.0; contrib = 2.0*2.0 = 4.0
    # idio = 2.0 - 4.0 - 0.0 = -2.0
    assert out["stock_return_pct"] == 2.0
    assert out["market_contrib_pct"] == 4.0
    assert out["industry_contrib_pct"] == 0.0
    assert out["idio_return_pct"] == -2.0
    assert out["idio_return_pct"] == out["stock_return_pct"] - out["market_contrib_pct"]


def test_idio_preserved_when_industry_proxy_missing() -> None:
    """Call-site rule: null industry_contrib only; idio always from decomp."""
    decomp = _decompose_window([0.03, -0.01], [0.01, 0.01], None, beta=2.0)
    ind_win = None
    industry_contrib_pct = decomp["industry_contrib_pct"] if ind_win is not None else None
    idio_return_pct = decomp["idio_return_pct"]
    assert industry_contrib_pct is None
    assert idio_return_pct == -2.0
    assert idio_return_pct == decomp["stock_return_pct"] - decomp["market_contrib_pct"]


def test_ols_beta_pre_window_sample() -> None:
    """β estimated on pre-window returns does not include attribution window."""
    # 20 estimation days + 5 attribution days; y = 1.5 * x on estimation slice.
    est_x = [0.01 * (i % 3 - 1) for i in range(20)]
    est_y = [1.5 * v for v in est_x]
    attr_x = [0.02, -0.01, 0.03, 0.0, -0.02]
    attr_y = [0.99 * v for v in attr_x]  # deliberately off-beta in window
    x = est_x + attr_x
    y = est_y + attr_y
    win = 5
    beta, _ = _ols_beta(y[:-win], x[:-win])
    assert abs(beta - 1.5) < 1e-9
    decomp = _decompose_window(y[-win:], x[-win:], None, beta=beta)
    assert decomp["idio_return_pct"] == round(
        decomp["stock_return_pct"] - decomp["market_contrib_pct"], 4
    )


def test_attach_peaks_marks_unexplained_without_event() -> None:
    peaks = [ImpactPeakDayOut(date="2026-06-01", idio_return_pct=3.0)]
    out = _attach_peaks_from_events(peaks, events=[])
    assert out[0].unexplained is True
    assert out[0].event_title is None


def test_attach_peaks_links_same_day_event() -> None:
    peaks = [ImpactPeakDayOut(date="2026-06-01", idio_return_pct=3.0)]
    events = [{"date": "2026-06-01", "title": "业绩预告", "kind": "earnings", "fwd_5d": 1.2}]
    out = _attach_peaks_from_events(peaks, events)
    assert out[0].unexplained is False
    assert out[0].event_title == "业绩预告"


def test_decompose_window_rounds_to_four_decimals() -> None:
    stock = [0.012345, 0.001]
    mkt = [0.005, 0.002]
    out = _decompose_window(stock, mkt, None, beta=1.0)
    for v in out.values():
        # rounded to 4 decimals → at most 4 decimal places
        assert round(v, 4) == v


def test_daily_rets_basic() -> None:
    assert _daily_rets([100.0, 110.0, 99.0]) == pytest.approx([0.1, -0.1])
    assert _daily_rets([100.0]) == []


def test_daily_rets_zero_when_prev_non_positive() -> None:
    # prev == 0 → 0.0；其余照常计算
    assert _daily_rets([100.0, 0.0, 110.0]) == [-1.0, 0.0]


def test_peer_ew_returns_none_for_empty() -> None:
    assert _peer_ew_returns([], ["2026-06-01"]) is None


def test_peer_ew_returns_none_when_all_dropped() -> None:
    # 少于 2 根的 peer 被丢弃 → None
    bars = [_bars_from([("2026-06-01T00:00:00", 10.0)])]
    assert _peer_ew_returns(bars, ["2026-06-02"]) is None


def test_peer_ew_returns_skips_non_positive_close() -> None:
    # close=0 的 bar 不入 map → by_date 不足 2 → 丢弃 → None
    peer = _bars_from([("2026-06-01", 0.0), ("2026-06-02", 110.0)])
    assert _peer_ew_returns([peer], ["2026-06-02"]) is None


def test_peer_ew_returns_aligned_basket() -> None:
    peer1 = _bars_from([("2026-06-01", 100.0), ("2026-06-02", 110.0), ("2026-06-03", 99.0)])
    peer2 = _bars_from([("2026-06-02", 50.0), ("2026-06-03", 55.0)])
    dates = ["2026-06-01", "2026-06-02", "2026-06-03"]
    out = _peer_ew_returns([peer1, peer2], dates)
    assert out is not None
    # 06-01 无 peer 收益 → 0.0；06-02 → 0.1；06-03 → (-0.1 + 0.1) / 2 = 0.0
    assert out == pytest.approx([0.0, 0.1, 0.0])


def test_normalize_event_from_dataclass() -> None:
    ev = EventStudyEventOut(
        title="业绩预告",
        event_kind="earnings",
        event_date="2026-06-01T00:00:00+08:00",
        returns={"5": 1.5},
    )
    norm = _normalize_event_for_peak(ev)
    assert norm["date"] == "2026-06-01"
    assert norm["title"] == "业绩预告"
    assert norm["kind"] == "earnings"
    assert norm["fwd_5d"] == 1.5


def test_top_idio_peak_days_picks_abs_largest() -> None:
    dates = ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05"]
    stock = [0.01, -0.05, 0.0, 0.02, 0.03]
    mkt = [0.0, 0.0, 0.0, 0.0, 0.0]
    peaks = _top_idio_peak_days(dates, stock, mkt, None, beta=1.0, top_n=3)
    assert [p.date for p in peaks] == ["2026-06-02", "2026-06-05", "2026-06-04"]


def test_top_idio_peak_days_with_industry() -> None:
    dates = ["2026-06-01", "2026-06-02"]
    stock = [0.05, -0.03]
    mkt = [0.02, 0.01]
    ind = [0.01, 0.0]
    peaks = _top_idio_peak_days(dates, stock, mkt, ind, beta=1.0, top_n=1)
    # 06-01 idio = (0.05 - 0.02 - 0.01)*100 = 2.0；06-02 = (-0.03 - 0.01)*100 = -4.0
    assert peaks[0].date == "2026-06-02"
    assert peaks[0].idio_return_pct == -4.0


@pytest.mark.asyncio
async def test_attach_impact_events_noop_without_peaks() -> None:
    impact = ImpactOut(peak_days=[])
    out = await attach_impact_events(impact, "600000")
    assert out is impact


@pytest.mark.asyncio
async def test_attach_impact_events_with_peaks(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_study(symbol: str, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            events=[{"date": "2026-06-01", "title": "业绩预告", "kind": "earnings", "fwd_5d": 0.8}]
        )

    monkeypatch.setattr("stockresearch.services.impact.compute_event_study", fake_study)
    impact = ImpactOut(peak_days=[ImpactPeakDayOut(date="2026-06-01", idio_return_pct=3.0)])
    out = await attach_impact_events(impact, "600000")
    assert out.peak_days[0].event_title == "业绩预告"
    assert out.peak_days[0].unexplained is False


@pytest.mark.asyncio
async def test_attach_peaks_from_event_study_failure_marks_unexplained(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("network down")

    monkeypatch.setattr("stockresearch.services.impact.compute_event_study", boom)
    peaks = [ImpactPeakDayOut(date="2026-06-01", idio_return_pct=3.0)]
    out = await _attach_peaks_from_event_study("600000", peaks)
    assert out[0].unexplained is True
    assert out[0].event_title is None


@pytest.mark.asyncio
async def test_attach_peaks_from_event_study_links_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_study(symbol: str, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            events=[
                {
                    "date": "2026-06-01",
                    "title": "业绩预告",
                    "kind": "earnings",
                    "fwd_5d": 1.2,
                }
            ]
        )

    monkeypatch.setattr("stockresearch.services.impact.compute_event_study", fake_study)
    peaks = [ImpactPeakDayOut(date="2026-06-01", idio_return_pct=3.0)]
    out = await _attach_peaks_from_event_study("600000", peaks)
    assert out[0].unexplained is False
    assert out[0].event_title == "业绩预告"
    assert out[0].event_kind == "earnings"
    assert out[0].event_fwd_return_5d_pct == 1.2


# ── compute_impact 分支（mock 网络路径） ──────────────────────
def _mk_dates(n: int, start: str = "2026-05-01") -> list[str]:
    d = date.fromisoformat(start)
    return [(d + timedelta(days=i)).isoformat() for i in range(n)]


def _bars(dates: list[str], base: float, step: float) -> list[dict[str, float | str]]:
    return [{"date": d, "close": round(base + step * i, 4)} for i, d in enumerate(dates)]


def _bars_from(rows: list[tuple[str, float]]) -> list[dict[str, float | str]]:
    return [{"date": d, "close": c} for d, c in rows]


def _patch_impact_paths(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stock_bars: list[dict[str, float | str]],
    mkt_bars: list[dict[str, float | str]] | None = None,
    peer_bars: list[list[dict[str, float | str]]] | None = None,
    peer_symbols: list[str] | None = None,
    event_dates: list[str] | None = None,
) -> None:
    """统一 mock impact 的 4 个网络入口。"""
    peers = [{"symbol": s} for s in (peer_symbols or [])]

    async def fake_meta(symbol: str, days: int) -> BarsMeta:
        if peer_symbols and symbol in peer_symbols:
            idx = peer_symbols.index(symbol)
            return BarsMeta(
                bars=peer_bars[idx] if peer_bars else [],
                source="warehouse",
                adjust="qfq",
                as_of="2026-06-01",
            )
        return BarsMeta(
            bars=stock_bars,
            source="warehouse",
            adjust="qfq",
            as_of="2026-06-01",
        )

    async def fake_kline(self: object, symbol: str, days: int) -> list[dict[str, float | str]]:
        return mkt_bars or []

    async def fake_peers(self: object, symbol: str) -> list[dict[str, str]]:
        return peers

    async def fake_study(symbol: str, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            events=[
                {"date": d, "title": "事件", "kind": "earnings", "fwd_5d": 0.5}
                for d in (event_dates or [])
            ]
        )

    monkeypatch.setattr("stockresearch.services.impact.get_bars_meta_for_symbol", fake_meta)
    monkeypatch.setattr(
        "stockresearch.data.providers.market.TechnicalDataProvider.get_kline_bars", fake_kline
    )
    monkeypatch.setattr(
        "stockresearch.data.providers.market.FinancialDataProvider.get_industry_peers", fake_peers
    )
    monkeypatch.setattr("stockresearch.services.impact.compute_event_study", fake_study)


@pytest.mark.asyncio
async def test_compute_impact_stock_not_qfq(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_meta(symbol: str, days: int) -> BarsMeta:
        return BarsMeta(bars=[], source="x", adjust="none", as_of="2026-06-01")

    monkeypatch.setattr("stockresearch.services.impact.get_bars_meta_for_symbol", fake_meta)
    out = await compute_impact("600000")
    assert out.partial is True
    assert "stock_bars_not_qfq" in out.gaps
    assert out.stock_return_pct is None


@pytest.mark.asyncio
async def test_compute_impact_market_missing_leaves_beta_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_impact_paths(monkeypatch, stock_bars=_bars(_mk_dates(30), 100.0, 1.0))
    out = await compute_impact("600000", window=20)
    assert "market_bars_missing" in out.gaps
    assert "industry_proxy_insufficient" in out.gaps
    assert out.market_contrib_pct is None
    assert out.idio_return_pct is None
    assert out.stock_return_pct is not None
    assert out.partial is True


@pytest.mark.asyncio
async def test_compute_impact_full_path(monkeypatch: pytest.MonkeyPatch) -> None:
    dates = _mk_dates(70)
    peer_symbols = ["600001", "600002", "600003"]
    _patch_impact_paths(
        monkeypatch,
        stock_bars=_bars(dates, 100.0, 1.0),
        mkt_bars=_bars(dates, 4000.0, 10.0),
        peer_bars=[_bars(dates[i:], 50.0, 0.5) for i in (0, 1, 2)],
        peer_symbols=peer_symbols,
        event_dates=dates,
    )
    out = await compute_impact("600000", window=20)
    assert out.stock_return_pct is not None
    assert out.market_contrib_pct is not None
    assert out.industry_contrib_pct is not None
    assert out.idio_return_pct is not None
    assert out.r_squared is not None
    assert out.partial is False
    assert out.gaps == []
    assert len(out.peak_days) == 3
    # 事件 attach 已执行（event 日期在窗口内 → 应匹配到标题）
    matched = [p for p in out.peak_days if p.event_title == "事件"]
    assert matched or any(p.event_title is not None for p in out.peak_days)


@pytest.mark.asyncio
async def test_compute_impact_beta_overlaps_window(monkeypatch: pytest.MonkeyPatch) -> None:
    # 26 天 → 收益 25 点；win=20 → 窗内样本仅 5 点 < 15 → 回退全序列 β
    dates = _mk_dates(26)
    _patch_impact_paths(
        monkeypatch,
        stock_bars=_bars(dates, 100.0, 1.0),
        mkt_bars=_bars(dates, 4000.0, 10.0),
    )
    out = await compute_impact("600000", window=20)
    assert "beta_est_overlaps_window" in out.gaps
    assert out.partial is True
    assert out.market_contrib_pct is not None


@pytest.mark.asyncio
async def test_compute_impact_stock_bars_short(monkeypatch: pytest.MonkeyPatch) -> None:
    # 15 天 < window+1 → stock_bars_short；对齐样本 15 < 20 → aligned_sample_short
    stock_dates = _mk_dates(15)
    mkt_dates = _mk_dates(30)
    _patch_impact_paths(
        monkeypatch,
        stock_bars=_bars(stock_dates, 100.0, 1.0),
        mkt_bars=_bars(mkt_dates, 4000.0, 10.0),
    )
    out = await compute_impact("600000", window=20)
    assert "stock_bars_short" in out.gaps
    assert "aligned_sample_short" in out.gaps
    assert out.partial is True
    assert out.market_contrib_pct is None


@pytest.mark.asyncio
async def test_compute_impact_aligned_sample_too_short(monkeypatch: pytest.MonkeyPatch) -> None:
    # 市场 bar 仅 2 天且与个股日期零重叠 → 对齐样本 0 < 2 → 早退
    _patch_impact_paths(
        monkeypatch,
        stock_bars=_bars(_mk_dates(5), 100.0, 1.0),
        mkt_bars=_bars(_mk_dates(2, start="2026-01-01"), 4000.0, 10.0),
    )
    out = await compute_impact("600000", window=20)
    assert "aligned_sample_too_short" in out.gaps
    assert out.partial is True
