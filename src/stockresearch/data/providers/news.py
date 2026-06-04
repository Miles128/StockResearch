"""News provider — AkShare for real A-share news, parallel fetch with timeout."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import akshare as ak
import httpx

from stockresearch.core.config import get_settings
from stockresearch.utils.llm import get_llm_client

logger = logging.getLogger(__name__)

_AKSHARE_NEWS_TIMEOUT_SEC = 8.0


@dataclass(frozen=True)
class RawNewsItem:
    title: str
    content: str
    source: str
    published_at: datetime
    url: str = ""


class NewsProvider:
    async def fetch_latest(self, limit: int = 30) -> list[RawNewsItem]:
        if get_settings().use_mock_market_data:
            return _fallback_news(limit)
        items = await self._fetch_akshare_market(limit)
        if not items:
            items = await self._fetch_web_search(limit)
        if not items:
            items = _fallback_news(limit)
        return items

    async def fetch_for_user(
        self,
        symbol_pairs: list[tuple[str, str]],
        sectors: frozenset[str],
        limit: int = 30,
    ) -> list[RawNewsItem]:
        if get_settings().use_mock_market_data:
            return _fallback_news_for_user(symbol_pairs, sectors, limit)

        tasks: list[asyncio.Task[list[RawNewsItem]]] = []
        for symbol, name in symbol_pairs[:8]:
            query = name or symbol
            if query:
                tasks.append(asyncio.create_task(self._fetch_akshare_symbol(query, 4)))
        for sector in list(sectors)[:6]:
            tasks.append(asyncio.create_task(self._fetch_akshare_symbol(sector, 4)))
        tasks.append(asyncio.create_task(self._fetch_akshare_market(max(5, limit // 4))))

        items: list[RawNewsItem] = []
        if tasks:
            batches = await asyncio.gather(*tasks, return_exceptions=True)
            for batch in batches:
                if isinstance(batch, list):
                    items.extend(batch)

        items = _dedupe_items(items)
        if not items:
            items = await self._fetch_web_search(limit)
        if not items:
            items = _fallback_news_for_user(symbol_pairs, sectors, limit)
        return items[: limit * 2]

    async def _fetch_akshare_market(self, limit: int) -> list[RawNewsItem]:
        return await self._fetch_akshare(symbol="全部", limit=limit)

    async def _fetch_akshare_symbol(self, query: str, limit: int) -> list[RawNewsItem]:
        if not query:
            return []
        return await self._fetch_akshare(symbol=query, limit=limit)

    async def _fetch_akshare(self, symbol: str, limit: int) -> list[RawNewsItem]:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._fetch_akshare_sync, symbol, limit),
                timeout=_AKSHARE_NEWS_TIMEOUT_SEC,
            )
        except TimeoutError:
            logger.warning("AkShare news timed out for %s", symbol)
            return []
        except Exception as exc:
            logger.warning("AkShare news fetch failed for %s: %s", symbol, exc)
            return []

    def _fetch_akshare_sync(self, symbol: str, limit: int) -> list[RawNewsItem]:
        df = ak.stock_news_em(symbol=symbol)
        items: list[RawNewsItem] = []
        for _, row in df.head(limit).iterrows():
            title = str(row.get("新闻标题", "")).strip()
            if not title:
                continue
            content = str(row.get("新闻内容", ""))
            source = str(row.get("文章来源", "东方财富"))
            url = str(row.get("新闻链接", ""))
            pub_time = row.get("发布时间", "")
            published_at = _parse_datetime(pub_time) if pub_time else datetime.now(UTC)
            items.append(
                RawNewsItem(
                    title=title,
                    content=content[:500],
                    source=source,
                    published_at=published_at,
                    url=url,
                )
            )
        return items

    async def _fetch_web_search(self, limit: int) -> list[RawNewsItem]:
        llm = get_llm_client()
        if llm.__class__.__name__ == "MockLLMClient":
            return []
        try:
            settings = get_settings()
            if not settings.llm_api_key:
                return []
            headers = {"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json"}
            payload = {
                "model": settings.llm_model,
                "messages": [
                    {"role": "system", "content": "你是财经新闻搜索助手，列出最近3条A股市场重要新闻。每行一条，格式：标题|来源"},
                    {"role": "user", "content": "请列出今天A股市场最重要的新闻"},
                ],
                "temperature": 0.3,
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            items: list[RawNewsItem] = []
            for line in content.strip().split("\n"):
                line = line.strip().lstrip("0123456789.-) ")
                if not line:
                    continue
                parts = line.split("|")
                title = parts[0].strip()
                source = parts[1].strip() if len(parts) > 1 else "AI生成(非真实新闻)"
                items.append(
                    RawNewsItem(
                        title=title,
                        content=title,
                        source=source,
                        published_at=datetime.now(UTC),
                    )
                )
            return items[:limit]
        except Exception as exc:
            logger.warning("Web search news failed: %s", exc)
            return []


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(value, fmt)
                return dt.replace(tzinfo=UTC)
            except ValueError:
                continue
    return datetime.now(UTC)


def _dedupe_items(items: list[RawNewsItem]) -> list[RawNewsItem]:
    seen: set[str] = set()
    result: list[RawNewsItem] = []
    for item in items:
        key = item.title.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _fallback_news_for_user(
    symbol_pairs: list[tuple[str, str]],
    sectors: frozenset[str],
    limit: int,
) -> list[RawNewsItem]:
    items = _fallback_news(limit * 2)
    symbols = {symbol for symbol, _ in symbol_pairs}
    names = {name for _, name in symbol_pairs if name}
    filtered: list[RawNewsItem] = []
    for item in items:
        text = f"{item.title} {item.content}"
        is_market = any(kw in text for kw in ("央行", "北向", "A股", "大盘", "沪指"))
        is_symbol = any(symbol in text for symbol in symbols)
        is_name = any(name in text for name in names)
        is_sector = any(sector in text for sector in sectors)
        if is_market or is_symbol or is_name or is_sector:
            filtered.append(item)
    return filtered[:limit] if filtered else items[: min(3, limit)]


def _fallback_news(limit: int) -> list[RawNewsItem]:
    now = datetime.now(UTC)
    samples = [
        ("央行开展逆回购操作，流动性保持合理充裕", "market", "neutral"),
        ("宁德时代发布新一代电池技术进展", "300750", "bullish"),
        ("贵州茅台公布年度分红方案", "600519", "bullish"),
        ("半导体设备国产化加速", "半导体", "bullish"),
        ("北向资金今日净流入超50亿元", "market", "bullish"),
    ]
    result: list[RawNewsItem] = []
    for title, entity, _ in samples[:limit]:
        result.append(
            RawNewsItem(
                title=title,
                content=f"{title}。相关：{entity}",
                source="fallback",
                published_at=now,
            )
        )
    return result
