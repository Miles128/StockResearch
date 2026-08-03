"""Trading rule provider — ST/suspension/limit status from Sina quotes."""

from stockresearch.data.providers.base import run_sync_fetch
from stockresearch.data.providers.market.common import (
    _QUOTE_TIMEOUT_SEC,
    _as_float,
    _use_mock_market_data,
)
from stockresearch.data.providers.sina_quote import QuoteRow, fetch_sina_quotes
from stockresearch.utils.symbols import resolve_name


class MarketRuleProvider:
    async def get_trading_rules(self, symbol: str) -> dict[str, object]:
        if _use_mock_market_data():
            return {
                "source": "mock",
                "verified": True,
                "status": "normal",
                "is_st": False,
                "is_suspended": False,
                "is_limit_up": False,
                "is_limit_down": False,
                "limit_pct": self._limit_pct(symbol, resolve_name(symbol)),
                "missing": [],
            }
        rows = await run_sync_fetch(
            f"sina trading rules {symbol}",
            lambda: fetch_sina_quotes([symbol]),
            timeout=_QUOTE_TIMEOUT_SEC,
            fallback={},
        )
        row = rows.get(symbol) if rows else None
        if not row:
            return {
                "source": "sina_quote",
                "verified": False,
                "status": "unknown",
                "is_st": False,
                "is_suspended": False,
                "is_limit_up": False,
                "is_limit_down": False,
                "limit_pct": self._limit_pct(symbol, ""),
                "missing": ["无法获取涨跌停、ST、停复牌状态"],
            }
        return self._row_to_trading_rules(symbol, row, source="sina_quote")

    def _row_to_trading_rules(
        self,
        symbol: str,
        row: QuoteRow,
        *,
        source: str,
    ) -> dict[str, object]:
        name = str(row.get("name", resolve_name(symbol)))
        price = _as_float(row.get("price"))
        prev_close = _as_float(row.get("prev_close"))
        open_price = _as_float(row.get("open"))
        volume = _as_float(row.get("volume"))
        is_st = "ST" in name.upper() or "退" in name
        is_suspended = price <= 0 or (open_price <= 0 and volume <= 0)
        limit_pct = self._limit_pct(symbol, name)
        upper = prev_close * (1 + limit_pct / 100) if prev_close else 0
        lower = prev_close * (1 - limit_pct / 100) if prev_close else 0
        tolerance = max(0.01, prev_close * 0.001)
        is_limit_up = bool(prev_close and price and price >= upper - tolerance)
        is_limit_down = bool(prev_close and price and price <= lower + tolerance)
        if is_suspended:
            status = "suspended"
        elif is_limit_up:
            status = "limit_up"
        elif is_limit_down:
            status = "limit_down"
        else:
            status = "normal"
        return {
            "source": source,
            "verified": True,
            "status": status,
            "name": name,
            "is_st": is_st,
            "is_suspended": is_suspended,
            "is_limit_up": is_limit_up,
            "is_limit_down": is_limit_down,
            "limit_pct": limit_pct,
            "prev_close": prev_close,
            "price": price,
            "upper_limit": round(upper, 2) if upper else None,
            "lower_limit": round(lower, 2) if lower else None,
            "missing": [],
        }

    @staticmethod
    def _limit_pct(symbol: str, name: str) -> float:
        upper_name = name.upper()
        if "ST" in upper_name or "退" in name:
            return 5.0
        if symbol.startswith(("300", "301", "688", "689")):
            return 20.0
        if symbol.startswith(("4", "8")):
            return 30.0
        return 10.0
