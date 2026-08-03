"""Overseas/global market indices — Sina ``hq.sinajs.cn`` ``int_*`` codes.

Graceful degradation: any failure or timeout returns an empty list and never
raises, so callers can treat overseas data as optional enrichment.
"""

import asyncio
import logging
from dataclasses import asdict, dataclass

import httpx

from stockresearch.services.provider_cache_policy import DEFAULT_QUOTE_CACHE_TTL_SECONDS
from stockresearch.services.sqlite_cache import get_sqlite_cached, set_sqlite_cached

logger = logging.getLogger(__name__)

# (sina code, display name) — display name wins over payload name for stability.
_GLOBAL_INDEX_LIST = (
    ("int_hangseng", "恒生指数"),
    ("int_dji", "道琼斯"),
    ("int_nasdaq", "纳斯达克"),
    ("int_sp500", "标普500"),
    ("int_nikkei", "日经225"),
)

_CACHE_KEY = "market:global_indices"
_FETCH_TIMEOUT_SEC = 5.0

_MOCK_INDICES = [
    ("恒生指数", 26000.0, 0.48),
    ("道琼斯", 46200.0, 0.65),
    ("纳斯达克", 22480.0, 0.44),
    ("标普500", 6640.0, 0.59),
    ("日经225", 44900.0, -0.90),
]


@dataclass(frozen=True)
class GlobalIndexQuote:
    name: str
    price: float
    change_pct: float


def _parse_pct(raw: str) -> float:
    """Parse change percent defensively — payload may carry a trailing '%'."""
    return float(raw.strip().rstrip("%"))


def _parse_sina_global_response(text: str) -> list[GlobalIndexQuote]:
    by_sina_code = {code: name for code, name in _GLOBAL_INDEX_LIST}
    results: list[GlobalIndexQuote] = []
    for line in text.strip().split(";"):
        if "hq_str_" not in line:
            continue
        _, _, remainder = line.partition("hq_str_")
        sina_code, _, rest = remainder.partition("=")
        payload = rest.strip().strip('"')
        if not payload:
            continue
        parts = [p.strip() for p in payload.split(",")]
        # 实测格式: "名称,现价,涨跌额,涨跌幅"（涨跌幅偶带 %）
        if len(parts) < 4:
            continue
        label = by_sina_code.get(sina_code)
        if label is None:
            continue
        try:
            price = float(parts[1])
            change_pct = _parse_pct(parts[3])
        except ValueError:
            continue
        results.append(GlobalIndexQuote(name=label, price=price, change_pct=change_pct))
    return results


def fetch_sina_global_indices() -> list[GlobalIndexQuote]:
    codes = ",".join(code for code, _ in _GLOBAL_INDEX_LIST)
    url = f"https://hq.sinajs.cn/list={codes}"
    headers = {"Referer": "https://finance.sina.com.cn"}

    with httpx.Client(timeout=5.0) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        text = resp.content.decode("gbk", errors="ignore")

    results = _parse_sina_global_response(text)
    if not results:
        raise ValueError("Sina global index response empty")
    return results


class GlobalMarketsProvider:
    """Overseas index quotes. Always returns a list (possibly empty)."""

    async def get_indices(
        self,
        *,
        cache_ttl_seconds: int | None = None,
    ) -> list[GlobalIndexQuote]:
        from stockresearch.core.config import get_settings

        if get_settings().use_mock_market_data:
            return [
                GlobalIndexQuote(name=name, price=price, change_pct=change_pct)
                for name, price, change_pct in _MOCK_INDICES
            ]

        ttl = cache_ttl_seconds or DEFAULT_QUOTE_CACHE_TTL_SECONDS
        cached = get_sqlite_cached(_CACHE_KEY)
        if cached is not None:
            rows = _rows_from_cache_payload(cached)
            if rows:
                return rows

        try:
            rows = await asyncio.wait_for(
                asyncio.to_thread(fetch_sina_global_indices),
                timeout=_FETCH_TIMEOUT_SEC,
            )
        except TimeoutError:
            logger.warning("Sina global indices timed out")
            return []
        except Exception as exc:
            logger.warning("Sina global indices failed: %s", exc)
            return []

        if rows:
            set_sqlite_cached(
                _CACHE_KEY,
                {"rows": [asdict(row) for row in rows], "source": "sina"},
                ttl,
            )
        return rows


def _rows_from_cache_payload(payload: dict[str, object]) -> list[GlobalIndexQuote]:
    raw_rows = payload.get("rows")
    if not isinstance(raw_rows, list):
        return []
    rows: list[GlobalIndexQuote] = []
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        try:
            rows.append(
                GlobalIndexQuote(
                    name=str(item.get("name", "")),
                    price=float(item.get("price")),  # type: ignore[arg-type]
                    change_pct=float(item.get("change_pct")),  # type: ignore[arg-type]
                )
            )
        except (TypeError, ValueError):
            continue
    return rows


def format_global_snapshot(rows: list[GlobalIndexQuote]) -> str:
    """Format overseas indices for prompts; empty string when unavailable."""
    lines: list[str] = []
    for quote in rows:
        arrow = "↑" if quote.change_pct > 0 else "↓" if quote.change_pct < 0 else "→"
        lines.append(f"{quote.name}: {quote.price:.2f} {arrow} {quote.change_pct:+.2f}%")
    return "\n".join(lines)
