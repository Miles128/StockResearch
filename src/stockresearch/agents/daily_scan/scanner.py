"""Daily technical scan for a portfolio of holdings."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Literal

from stockresearch.core.constants import DISCLAIMER
from stockresearch.core.schemas import DailyScanItem, DailyScanOut
from stockresearch.data.providers.market import QuoteProvider, TechnicalDataProvider
from stockresearch.db.models import Holding
from stockresearch.services.holding_metrics import profit_pct


def _signal_text(signal: Literal["bullish", "neutral", "bearish"]) -> str:
    return {"bullish": "偏多", "bearish": "偏空", "neutral": "中性"}.get(signal, "中性")


def _score_holding(
    symbol: str,
    name: str,
    sector: str,
    price: float | None,
    cost_price: float,
    bars: list[dict[str, float | str]],
) -> DailyScanItem:
    from stockresearch.data.technical_indicators import (
        macd_series,
        ma_series,
        rsi_series,
    )

    factors: list[str] = []
    closes = [float(b["close"]) for b in bars if b.get("close") is not None]
    if not closes or price is None:
        return DailyScanItem(
            symbol=symbol,
            name=name,
            sector=sector,
            price=price,
            change_pct=None,
            cost_price=cost_price,
            profit_pct=profit_pct(cost_price, price) if price else None,
            technical_score=50,
            signal="neutral",
            signal_text="中性",
            suggestion="数据不足，无法给出技术判断",
            factors=["缺少 K 线数据"],
        )

    latest_close = closes[-1]
    ma20_series = ma_series(closes, 20)
    ma60_series = ma_series(closes, 60)
    ma20 = ma20_series[-1] if ma20_series else None
    ma60 = ma60_series[-1] if ma60_series else None
    rsi_series_val = rsi_series(closes)
    rsi = rsi_series_val[-1] if rsi_series_val else None
    macd = macd_series(closes)
    macd_hist = macd["histogram"][-1] if macd.get("histogram") else None
    prev_macd_hist = macd["histogram"][-2] if macd.get("histogram") and len(macd["histogram"]) > 1 else None

    score = 50

    # Trend relative to moving averages
    if ma20 is not None and ma60 is not None:
        if latest_close > ma20 > ma60:
            score += 15
            factors.append(f"收盘价站上 MA20({ma20:.2f}) 与 MA60({ma60:.2f})")
        elif latest_close < ma20 < ma60:
            score -= 15
            factors.append(f"收盘价跌破 MA20({ma20:.2f}) 与 MA60({ma60:.2f})")
        elif latest_close > ma20:
            score += 5
            factors.append(f"收盘价位于 MA20({ma20:.2f}) 之上")
        elif latest_close < ma20:
            score -= 5
            factors.append(f"收盘价位于 MA20({ma20:.2f}) 之下")
        else:
            factors.append(f"MA20={ma20:.2f}, MA60={ma60:.2f}")
    else:
        factors.append("均线数据不足")

    # RSI momentum
    if rsi is not None:
        if rsi >= 70:
            score -= 10
            factors.append(f"RSI={rsi:.1f} 进入超买区间")
        elif rsi <= 30:
            score += 10
            factors.append(f"RSI={rsi:.1f} 进入超卖区间")
        elif rsi > 50:
            score += 5
            factors.append(f"RSI={rsi:.1f} 偏强")
        else:
            score -= 5
            factors.append(f"RSI={rsi:.1f} 偏弱")
    else:
        factors.append("RSI 数据不足")

    # MACD histogram
    if macd_hist is not None:
        if macd_hist > 0:
            score += 8
            factors.append(f"MACD 红柱={macd_hist:.3f}")
        else:
            score -= 8
            factors.append(f"MACD 绿柱={macd_hist:.3f}")
        if prev_macd_hist is not None:
            if macd_hist > prev_macd_hist:
                score += 4
                factors.append("MACD 柱在扩大")
            else:
                score -= 4
                factors.append("MACD 柱在收敛")
    else:
        factors.append("MACD 数据不足")

    # Price change
    change_pct = (latest_close - closes[-2]) / closes[-2] * 100 if len(closes) > 1 else 0.0
    if change_pct >= 5:
        score += 8
        factors.append(f"当日大涨 {change_pct:.2f}%")
    elif change_pct <= -5:
        score -= 8
        factors.append(f"当日大跌 {change_pct:.2f}%")
    elif change_pct > 0:
        score += 3
        factors.append(f"当日上涨 {change_pct:.2f}%")
    elif change_pct < 0:
        score -= 3
        factors.append(f"当日下跌 {change_pct:.2f}%")

    # Profit / loss vs cost
    profit = profit_pct(cost_price, latest_close)
    if profit is not None:
        if profit <= -10:
            score -= 10
            factors.append(f"较成本回撤 {profit:.2f}%")
        elif profit <= -5:
            score -= 5
            factors.append(f"较成本回撤 {profit:.2f}%")
        elif profit >= 10:
            score += 5
            factors.append(f"较成本盈利 {profit:.2f}%")

    technical_score = max(0, min(100, score))
    if technical_score >= 60:
        signal: Literal["bullish", "neutral", "bearish"] = "bullish"
    elif technical_score <= 40:
        signal = "bearish"
    else:
        signal = "neutral"

    suggestion = _build_suggestion(signal, ma20, ma60, rsi, macd_hist, profit)

    return DailyScanItem(
        symbol=symbol,
        name=name,
        sector=sector,
        price=round(latest_close, 2),
        change_pct=round(change_pct, 2),
        cost_price=round(cost_price, 2),
        profit_pct=round(profit, 2) if profit is not None else None,
        technical_score=technical_score,
        signal=signal,
        signal_text=_signal_text(signal),
        suggestion=suggestion,
        factors=factors,
    )


def _build_suggestion(
    signal: Literal["bullish", "neutral", "bearish"],
    ma20: float | None,
    ma60: float | None,
    rsi: float | None,
    macd_hist: float | None,
    profit: float | None,
) -> str:
    parts: list[str] = []
    if signal == "bullish":
        parts.append("技术面偏多，可持有或逢回调加仓")
    elif signal == "bearish":
        parts.append("技术面偏空，建议控制仓位或减仓")
    else:
        parts.append("技术面中性，建议观望")

    if rsi is not None and rsi >= 70:
        parts.append("RSI 超买，注意短期回调风险")
    elif rsi is not None and rsi <= 30:
        parts.append("RSI 超卖，或有反弹机会")

    if macd_hist is not None and macd_hist > 0:
        parts.append("MACD 红柱，动能偏强")
    elif macd_hist is not None and macd_hist <= 0:
        parts.append("MACD 绿柱，动能偏弱")

    if profit is not None and profit <= -8:
        parts.append("回撤较大，建议关注止损")

    if ma20 is not None and ma60 is not None:
        if ma20 > ma60:
            parts.append("短期均线在长期均线上方")
        else:
            parts.append("短期均线在长期均线下方")

    return "；".join(parts)


async def _scan_one(holding: Holding) -> DailyScanItem:
    try:
        quote = await QuoteProvider().get_quote(holding.symbol)
        price = quote.price
    except Exception:
        price = None

    try:
        bars = await TechnicalDataProvider().get_kline_bars(holding.symbol, days=60)
    except Exception:
        bars = []

    return _score_holding(
        symbol=holding.symbol,
        name=holding.name,
        sector=holding.sector,
        price=price,
        cost_price=float(holding.cost_price),
        bars=bars,
    )


async def run_daily_scan(holdings: list[Holding]) -> DailyScanOut:
    if not holdings:
        return DailyScanOut(
            scan_date=date.today(),
            summary="当前没有持仓，无法生成扫描报告",
            items=[],
            disclaimer=DISCLAIMER,
        )

    items = await asyncio.gather(*[_scan_one(h) for h in holdings])
    sorted_items = sorted(items, key=lambda x: x.technical_score, reverse=True)

    bullish = sum(1 for i in sorted_items if i.signal == "bullish")
    bearish = sum(1 for i in sorted_items if i.signal == "bearish")
    neutral = len(sorted_items) - bullish - bearish

    summary = (
        f"共扫描 {len(sorted_items)} 只持仓，"
        f"偏多 {bullish} 只，偏空 {bearish} 只，中性 {neutral} 只。"
    )
    if bearish > bullish:
        summary += "整体技术面偏弱，建议关注持仓风险。"
    elif bullish > bearish:
        summary += "整体技术面偏强，可维持现有仓位。"
    else:
        summary += "整体技术信号平衡，建议按个股信号操作。"

    return DailyScanOut(
        scan_date=date.today(),
        summary=summary,
        items=sorted_items,
        disclaimer=DISCLAIMER,
    )
