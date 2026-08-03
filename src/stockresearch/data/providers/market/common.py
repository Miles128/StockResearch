"""Market provider shared primitives — Quote model, mock data, parse helpers."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from stockresearch.core.config import get_settings
from stockresearch.utils.symbols import resolve_name

logger = logging.getLogger(__name__)

_QUOTE_TIMEOUT_SEC = 6.0
_DATA_TIMEOUT_SEC = 8.0

_POSITIVE_NEWS = ("增长", "利好", "超预期", "分红", "回购", "上涨", "突破", "中标")
_NEGATIVE_NEWS = ("下滑", "亏损", "减持", "问询", "立案", "下调", "警示", "违规", "解禁")


def _as_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, datetime):
        return default
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _as_datetime(value: object) -> datetime:
    return value if isinstance(value, datetime) else datetime.now(UTC)


def _market_code(symbol: str) -> str:
    if symbol.startswith("6"):
        return "sh"
    if symbol.startswith(("4", "8")):
        return "bj"
    return "sz"


@dataclass(frozen=True)
class Quote:
    symbol: str
    name: str
    price: float
    change_pct: float
    open: float
    high: float
    low: float
    volume: float
    updated_at: datetime


_MOCK_QUOTE_DEFAULTS: dict[str, tuple[float, str]] = {
    "600519": (1800.0, "贵州茅台"),
    "300750": (250.0, "宁德时代"),
    "601318": (50.0, "中国平安"),
}


def _use_mock_market_data() -> bool:
    return get_settings().use_mock_market_data


def _mock_quote(symbol: str) -> Quote:
    price, name = _MOCK_QUOTE_DEFAULTS.get(symbol, (100.0, resolve_name(symbol)))
    now = datetime.now(UTC)
    return Quote(
        symbol=symbol,
        name=name,
        price=price,
        change_pct=1.2,
        open=round(price * 0.99, 4),
        high=round(price * 1.02, 4),
        low=round(price * 0.98, 4),
        volume=1_000_000.0,
        updated_at=now,
    )


def _quote_to_cache(quote: Quote) -> dict[str, object]:
    return {
        "symbol": quote.symbol,
        "name": quote.name,
        "price": quote.price,
        "change_pct": quote.change_pct,
        "open": quote.open,
        "high": quote.high,
        "low": quote.low,
        "volume": quote.volume,
        "updated_at": quote.updated_at.isoformat(),
        "source": "cache",
    }


def _quote_from_cache(payload: dict[str, object]) -> Quote | None:
    try:
        updated_raw = payload.get("updated_at")
        updated_at = datetime.fromisoformat(str(updated_raw)) if updated_raw else datetime.now(UTC)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        return Quote(
            symbol=str(payload["symbol"]),
            name=str(payload.get("name", "")),
            price=_as_float(payload.get("price")),
            change_pct=_as_float(payload.get("change_pct")),
            open=_as_float(payload.get("open")),
            high=_as_float(payload.get("high")),
            low=_as_float(payload.get("low")),
            volume=_as_float(payload.get("volume")),
            updated_at=updated_at,
        )
    except (KeyError, TypeError, ValueError):
        return None
