"""Phase 10 L1 Impact — market / industry-proxy / idiosyncratic return decomposition.

Pure helpers (`_ols_beta`, `_decompose_window`, `_daily_rets`) are network-free
and unit-tested directly. `compute_impact` wires them to the daily-bar warehouse
(`get_bars_meta_for_symbol`, qfq required), the market index bars
(`TechnicalDataProvider.get_kline_bars` for `000300`), and the industry peer
EW proxy (`TechnicalDataProvider.get_industry_peers`).

Aggregation is **sum of simple daily returns × 100** for MVP
(`ImpactOut.model` carries `return_agg=sum_simple_pct`).
β is never fabricated: when the market series is missing or too short, the
market contribution (and downstream idio) are left `None` and the result is
marked partial. Event attachment to idio peaks is Task 3.
"""

from __future__ import annotations

import logging

from stockresearch.core.schemas import ImpactOut
from stockresearch.data.providers.market import TechnicalDataProvider
from stockresearch.services.daily_bars import get_bars_meta_for_symbol

logger = logging.getLogger(__name__)


def _ols_beta(y: list[float], x: list[float]) -> tuple[float, float]:
    """OLS β of y on x; returns (beta, r²). Falls back to (1.0, 0.0) when
    sample is too small or x has no variance (never fabricates a β)."""
    n = min(len(y), len(x))
    if n < 3:
        return 1.0, 0.0
    y, x = y[-n:], x[-n:]
    mx = sum(x) / n
    my = sum(y) / n
    var_x = sum((v - mx) ** 2 for v in x)
    if var_x <= 1e-18:
        return 1.0, 0.0
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True))
    beta = cov / var_x
    ss_tot = sum((b - my) ** 2 for b in y)
    ss_res = sum((b - (my + beta * (a - mx))) ** 2 for a, b in zip(x, y, strict=True))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-18 else 0.0
    return float(beta), float(max(0.0, min(1.0, r2)))


def _decompose_window(
    stock_rets: list[float],
    mkt_rets: list[float],
    ind_rets: list[float] | None,
    beta: float,
) -> dict[str, float]:
    """Sum-of-simple-returns × 100 attribution over the window.

    `industry_contrib` is the peer EW basket return (proxy, documented); when
    `ind_rets` is None the contribution is 0 and idio absorbs the residual.
    """
    stock_sum = sum(stock_rets) * 100.0
    mkt_sum = sum(mkt_rets) * 100.0
    ind_sum = sum(ind_rets) * 100.0 if ind_rets is not None else 0.0
    market_contrib = beta * mkt_sum
    industry_contrib = ind_sum
    idio = stock_sum - market_contrib - industry_contrib
    return {
        "stock_return_pct": round(stock_sum, 4),
        "market_contrib_pct": round(market_contrib, 4),
        "industry_contrib_pct": round(industry_contrib, 4),
        "idio_return_pct": round(idio, 4),
    }


def _daily_rets(closes: list[float]) -> list[float]:
    """Simple daily returns from a close-price series."""
    out: list[float] = []
    for i in range(1, len(closes)):
        prev, cur = closes[i - 1], closes[i]
        out.append((cur / prev - 1.0) if prev > 0 else 0.0)
    return out


def _peer_ew_returns(
    peer_bars: list[list[dict[str, float | str]]],
    dates: list[str],
) -> list[float] | None:
    """Equal-weight daily return series for the peer EW proxy, aligned to the
    stock/market calendar `dates` (inner join). Each peer contributes its
    simple daily return on dates where it has a bar; the basket return on a
    date is the mean of available peer returns on that date. Peers with fewer
    than 2 bars are dropped. Returns None when no peer survives."""
    if not peer_bars:
        return None
    # Build per-peer {date: close} maps.
    peer_series: list[dict[str, float]] = []
    for bars in peer_bars:
        if not bars or len(bars) < 2:
            continue
        by_date: dict[str, float] = {}
        for bar in bars:
            d = str(bar.get("date", ""))[:10]
            close = bar.get("close")
            if d and isinstance(close, (int, float)) and close > 0:
                by_date[d] = float(close)
        if len(by_date) >= 2:
            peer_series.append(by_date)
    if not peer_series:
        return None
    # Per-peer simple daily return keyed by date (return observed on date t
    # uses close[t] / close[t-1] where t-1 is the peer's previous bar).
    peer_rets: list[dict[str, float]] = []
    for by_date in peer_series:
        ordered = sorted(by_date.items())
        rets: dict[str, float] = {}
        for i in range(1, len(ordered)):
            d_prev, c_prev = ordered[i - 1]
            d_cur, c_cur = ordered[i]
            rets[d_cur] = (c_cur / c_prev - 1.0) if c_prev > 0 else 0.0
        peer_rets.append(rets)
    # Equal-weight average across peers, aligned to target dates.
    out: list[float] = []
    for d in dates:
        vals = [pr[d] for pr in peer_rets if d in pr]
        out.append(sum(vals) / len(vals)) if vals else out.append(0.0)
    return out


async def _load_peer_ew_returns(
    provider: TechnicalDataProvider,
    symbol: str,
    dates: list[str],
    window: int,
) -> tuple[list[float] | None, list[str]]:
    """Fetch industry peers, load each peer's qfq bars, and build the EW
    daily-return proxy aligned to `dates`. Returns (proxy_rets, gaps)."""
    gaps: list[str] = []
    try:
        peers = await provider.get_industry_peers(symbol)
    except Exception as exc:  # pragma: no cover - network path
        logger.warning("industry peers failed for %s: %s", symbol, exc)
        peers = []
    peer_symbols = [str(p.get("symbol", "")) for p in peers if p.get("symbol")]
    peer_bars: list[list[dict[str, float | str]]] = []
    for psym in peer_symbols[:6]:
        try:
            pm = await get_bars_meta_for_symbol(psym, days=window + 40)
            if pm.adjust == "qfq" and pm.bars:
                peer_bars.append(pm.bars)
        except Exception as exc:  # pragma: no cover - network path
            logger.debug("peer bars failed for %s: %s", psym, exc)
    if len(peer_bars) < 3:
        gaps.append("industry_proxy_insufficient")
        return None, gaps
    return _peer_ew_returns(peer_bars, dates), gaps


async def compute_impact(
    symbol: str,
    *,
    window: int = 20,
    market_symbol: str = "000300",
) -> ImpactOut:
    """L1 Impact decomposition over the last `window` trading days.

    Loads qfq stock bars, market index bars, and an industry peer EW proxy;
    aligns by calendar date (inner join); OLS-β of stock on market over the
    aligned estimation sample; then sums simple daily returns × 100 for the
    three contributions. Never fabricates β when market series is missing.
    """
    gaps: list[str] = []
    partial = False

    # 1. Stock qfq bars (need window + buffer for OLS estimation).
    stock_meta = await get_bars_meta_for_symbol(symbol, days=window + 40)
    if stock_meta.adjust != "qfq" or not stock_meta.bars:
        gaps.append("stock_bars_not_qfq")
        return ImpactOut(
            window_trading_days=window,
            market_symbol=market_symbol,
            partial=True,
            gaps=gaps,
            model="two_step_residual_v1;return_agg=sum_simple_pct",
        )
    stock_bars = stock_meta.bars
    if len(stock_bars) < window + 1:
        gaps.append("stock_bars_short")
        partial = True

    # 2. Market index bars (000300 by default).
    provider = TechnicalDataProvider()
    try:
        mkt_bars = await provider.get_kline_bars(market_symbol, days=window + 40)
    except Exception as exc:  # pragma: no cover - network path
        logger.warning("market index bars failed for %s: %s", market_symbol, exc)
        mkt_bars = []
    if not mkt_bars or len(mkt_bars) < 2:
        gaps.append("market_bars_missing")
        mkt_bars = []

    # 3. Industry peer EW proxy (built after date alignment).

    # 4. Align calendar dates (inner join on date string).
    stock_by_date = {str(b.get("date", ""))[:10]: b for b in stock_bars}
    mkt_by_date = {str(b.get("date", ""))[:10]: b for b in mkt_bars} if mkt_bars else {}
    common = sorted(set(stock_by_date) & (set(mkt_by_date) if mkt_by_date else set(stock_by_date)))
    if len(common) < window:
        gaps.append("aligned_sample_short")
        partial = True
    if len(common) < 2:
        gaps.append("aligned_sample_too_short")
        return ImpactOut(
            window_trading_days=window,
            market_symbol=market_symbol,
            partial=True,
            gaps=gaps,
            model="two_step_residual_v1;return_agg=sum_simple_pct",
        )

    stock_closes = [float(stock_by_date[d]["close"]) for d in common]
    stock_rets = _daily_rets(stock_closes)  # len = len(common) - 1

    # 5. OLS β on pre-window estimation sample when enough history exists;
    # attribute over the last `window` days. Fall back to full-series β with
    # gap `beta_est_overlaps_window` when pre-window sample < 15 points.
    mkt_rets: list[float] | None = None
    beta: float | None = None
    r2: float | None = None
    win = min(window, len(stock_rets))
    if mkt_by_date:
        mkt_closes = [float(mkt_by_date[d]["close"]) for d in common]
        mkt_rets_full = _daily_rets(mkt_closes)
        n = min(len(stock_rets), len(mkt_rets_full))
        est_stock = stock_rets[:-win] if win < n else []
        est_mkt = mkt_rets_full[:-win] if win < n else []
        est_n = min(len(est_stock), len(est_mkt))
        if est_n >= 15:
            beta_val, r2_val = _ols_beta(est_stock[-est_n:], est_mkt[-est_n:])
            beta, r2 = beta_val, r2_val
            mkt_rets = mkt_rets_full[-n:]
        elif n >= 15:
            gaps.append("beta_est_overlaps_window")
            partial = True
            beta_val, r2_val = _ols_beta(stock_rets[-n:], mkt_rets_full[-n:])
            beta, r2 = beta_val, r2_val
            mkt_rets = mkt_rets_full[-n:]
        else:
            gaps.append("market_beta_sample_short")
            partial = True

    # Peer EW proxy returns aligned to the same dates as the attribution window.
    ind_rets, peer_gaps = await _load_peer_ew_returns(
        provider, symbol, common[1:], window
    )
    gaps.extend(peer_gaps)

    # 6. Attribution over the last `window` days of the aligned return series.
    stock_win = stock_rets[-win:]
    mkt_win = mkt_rets[-win:] if mkt_rets is not None else None
    ind_win = ind_rets[-win:] if ind_rets is not None else None

    if beta is None or mkt_win is None:
        # Never fabricate β — leave market contrib + idio as None.
        gaps.append("market_contrib_unavailable")
        return ImpactOut(
            window_trading_days=window,
            stock_return_pct=round(sum(stock_win) * 100.0, 4),
            market_contrib_pct=None,
            industry_contrib_pct=round(sum(ind_win) * 100.0, 4) if ind_win is not None else None,
            idio_return_pct=None,
            model="two_step_residual_v1;return_agg=sum_simple_pct",
            r_squared=r2,
            market_symbol=market_symbol,
            partial=True,
            gaps=gaps,
        )

    decomp = _decompose_window(stock_win, mkt_win, ind_win, beta=beta)
    return ImpactOut(
        window_trading_days=window,
        stock_return_pct=decomp["stock_return_pct"],
        market_contrib_pct=decomp["market_contrib_pct"],
        industry_contrib_pct=decomp["industry_contrib_pct"] if ind_win is not None else None,
        idio_return_pct=decomp["idio_return_pct"],
        model="two_step_residual_v1;return_agg=sum_simple_pct",
        r_squared=r2,
        market_symbol=market_symbol,
        partial=partial,
        gaps=gaps,
    )
