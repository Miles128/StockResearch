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
from stockresearch.core.data_source_config import get_bocha_api_key
from stockresearch.utils.llm import _httpx_client_kwargs

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
        items = await self._fetch_akshare_market(limit)
        if not items:
            items = await self._fetch_web_search(limit)
        return items

    async def fetch_for_user(
        self,
        symbol_pairs: list[tuple[str, str]],
        sectors: frozenset[str],
        limit: int = 30,
    ) -> list[RawNewsItem]:
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
        """博查 AI 联网搜索兜底：当 AkShare / 东方财富均无数据时调用。

        文档：https://open.bochaai.com/documentation?algorithm=1
        Endpoint: POST https://api.bochaai.com/v1/web-search
        """
        settings = get_settings()
        api_key = (get_bocha_api_key() or settings.bocha_api_key or "").strip()
        if not api_key:
            return []
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "query": "A股 最新新闻 财经",
                "freshness": "oneDay",
                "summary": True,
                "count": max(limit, 10),
                "category": "general",
            }
            async with httpx.AsyncClient(**_httpx_client_kwargs()) as client:
                resp = await client.post(
                    "https://api.bochaai.com/v1/web-search",
                    headers=headers,
                    json=payload,
                    timeout=8.0,
                )
                resp.raise_for_status()
                data = resp.json()

            pages = data.get("webPages", {}) or {}
            rows = pages.get("value", []) or []
            items: list[RawNewsItem] = []
            for row in rows:
                title = str(row.get("name", "")).strip()
                if not title:
                    continue
                snippet = str(row.get("snippet", "")).strip()
                summary = str(row.get("summary", "")).strip()
                content = summary or snippet or title
                source = str(row.get("siteName", "")).strip() or "博查搜索"
                url = str(row.get("url", "")).strip()
                published_at = _parse_datetime(row.get("datePublished")) if row.get("datePublished") else datetime.now(UTC)
                items.append(
                    RawNewsItem(
                        title=title,
                        content=content[:500],
                        source=source,
                        published_at=published_at,
                        url=url,
                    )
                )
            return items[:limit]
        except Exception as exc:
            logger.warning("Bocha web search news failed: %s", exc)
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

