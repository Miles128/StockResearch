"""News provider — AkShare for real A-share news, parallel fetch with timeout."""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote

import akshare as ak
import httpx

try:
    from curl_cffi.requests import Session as CurlSession

    _HAS_CURL_CFFI = True
except ImportError:
    _HAS_CURL_CFFI = False

from stockresearch.core.config import get_settings
from stockresearch.utils.llm import _httpx_client_kwargs, get_llm_client

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
        items = _fetch_em_symbol_news_sync(symbol, limit)
        if items:
            return items
        try:
            df = ak.stock_news_em(symbol=symbol)
        except Exception as exc:
            logger.warning("AkShare stock_news_em failed for %s: %s", symbol, exc)
            return _fetch_em_global_news_sync(symbol, limit)
        result: list[RawNewsItem] = []
        for _, row in df.head(limit).iterrows():
            title = str(row.get("新闻标题", "")).strip()
            if not title:
                continue
            content = str(row.get("新闻内容", ""))
            source = str(row.get("文章来源", "东方财富"))
            url = str(row.get("新闻链接", ""))
            pub_time = row.get("发布时间", "")
            published_at = _parse_datetime(pub_time) if pub_time else datetime.now(UTC)
            result.append(
                RawNewsItem(
                    title=title,
                    content=content[:500],
                    source=source,
                    published_at=published_at,
                    url=url,
                )
            )
        if result:
            return result
        return _fetch_em_global_news_sync(symbol, limit)

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
            async with httpx.AsyncClient(**_httpx_client_kwargs()) as client:
                resp = await client.post(
                    settings.llm_base_url.strip(),
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


def _clean_em_news_text(value: object) -> str:
    text = str(value or "")
    text = re.sub(r"</?em>", "", text)
    text = text.replace("\u3000", "").replace("\r\n", " ")
    return text.strip()


def _fetch_em_symbol_news_sync(keyword: str, limit: int) -> list[RawNewsItem]:
    """Eastmoney search API — avoids broken akshare pyarrow replace on stock_news_em."""
    if not keyword:
        return []
    inner_param = {
        "uid": "",
        "keyword": keyword,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {
            "cmsArticleWebOld": {
                "searchScope": "default",
                "sort": "default",
                "pageIndex": 1,
                "pageSize": max(limit, 10),
                "preTag": "<em>",
                "postTag": "</em>",
            }
        },
    }
    params = {
        "cb": "jQuery_stockresearch",
        "param": json.dumps(inner_param, ensure_ascii=False),
        "_": str(int(datetime.now(UTC).timestamp() * 1000)),
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
        ),
        "Referer": f"https://so.eastmoney.com/news/s?keyword={quote(keyword)}",
    }
    try:
        if _HAS_CURL_CFFI:
            # curl_cffi impersonates browser TLS fingerprints
            with CurlSession(impersonate="chrome") as s:
                resp = s.get(
                    "https://search-api-web.eastmoney.com/search/jsonp",
                    params=params,
                    headers=headers,
                    timeout=8.0,
                )
        else:
            # fallback to httpx (may be blocked by anti-bot)
            resp = httpx.get(
                "https://search-api-web.eastmoney.com/search/jsonp",
                params=params,
                headers=headers,
                timeout=8.0,
            )
        resp.raise_for_status()
        payload = resp.text
        start = payload.find("(")
        end = payload.rfind(")")
        if start < 0 or end <= start:
            return []
        data = json.loads(payload[start + 1 : end])
        rows = data.get("result", {}).get("cmsArticleWebOld", [])
    except Exception as exc:
        logger.warning("Eastmoney symbol news failed for %s: %s", keyword, exc)
        return []

    items: list[RawNewsItem] = []
    for row in rows[:limit]:
        title = _clean_em_news_text(row.get("title"))
        if not title:
            continue
        content = _clean_em_news_text(row.get("content"))
        source = _clean_em_news_text(row.get("mediaName")) or "东方财富"
        code = str(row.get("code", "")).strip()
        url = f"http://finance.eastmoney.com/a/{code}.html" if code else ""
        published_at = _parse_datetime(row.get("date"))
        items.append(
            RawNewsItem(
                title=title,
                content=content[:500] or title,
                source=source,
                published_at=published_at,
                url=url,
            )
        )
    return items


def _fetch_em_global_news_sync(keyword: str, limit: int) -> list[RawNewsItem]:
    try:
        df = ak.stock_info_global_em()
    except Exception as exc:
        logger.warning("AkShare global news failed: %s", exc)
        return []
    items: list[RawNewsItem] = []
    for _, row in df.iterrows():
        title = str(row.get("标题", "")).strip()
        if not title or keyword not in title:
            continue
        summary = str(row.get("摘要", "")).strip()
        url = str(row.get("链接", "")).strip()
        published_at = _parse_datetime(row.get("发布时间"))
        items.append(
            RawNewsItem(
                title=title,
                content=(summary or title)[:500],
                source="东方财富全球",
                published_at=published_at,
                url=url,
            )
        )
        if len(items) >= limit:
            break
    return items


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
