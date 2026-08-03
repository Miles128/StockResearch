"""News provider — Eastmoney + multi-source flash + optional Bocha web-search."""

from __future__ import annotations

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
from stockresearch.data.providers.web_fetch import fetch_url_excerpt
from stockresearch.utils.llm import _httpx_client_kwargs

logger = logging.getLogger(__name__)

_AKSHARE_NEWS_TIMEOUT_SEC = 8.0
_ENRICH_LIMIT = 5


@dataclass(frozen=True)
class RawNewsItem:
    title: str
    content: str
    source: str
    published_at: datetime
    url: str = ""


class NewsProvider:
    async def fetch_latest(self, limit: int = 30) -> list[RawNewsItem]:
        items = await self._fetch_market_flash(limit)
        if _is_thin(items, limit):
            web = await self._fetch_web_search(limit, query="A股 最新新闻 财经")
            items = _dedupe_items([*items, *web])
        # Ingest path skips URL enrich (SLA); research/symbol path still enriches.
        return items[:limit]

    async def fetch_for_user(
        self,
        symbol_pairs: list[tuple[str, str]],
        sectors: frozenset[str],
        limit: int = 30,
    ) -> list[RawNewsItem]:
        tasks: list[asyncio.Task[list[RawNewsItem]]] = []
        queries: list[str] = []
        for symbol, name in symbol_pairs[:8]:
            query = name or symbol
            if query:
                queries.append(query)
                tasks.append(asyncio.create_task(self._fetch_akshare_symbol(query, 4)))
        for sector in list(sectors)[:6]:
            queries.append(sector)
            tasks.append(asyncio.create_task(self._fetch_akshare_symbol(sector, 4)))
        tasks.append(asyncio.create_task(self._fetch_market_flash(max(5, limit // 4))))

        items: list[RawNewsItem] = []
        if tasks:
            batches = await asyncio.gather(*tasks, return_exceptions=True)
            for batch in batches:
                if isinstance(batch, list):
                    items.extend(batch)

        items = _dedupe_items(items)
        if _is_thin(items, limit):
            # Symbol-aware Bocha when local sources are thin.
            focus = queries[0] if queries else "A股"
            web = await self._fetch_web_search(
                max(limit, 10),
                query=f"{focus} A股 新闻",
            )
            items = _dedupe_items([*items, *web])
        # Light enrich for user ingest (top 2 only).
        return await self._enrich_excerpts(items[: limit * 2], budget=2)

    async def fetch_symbol_news(
        self,
        query: str,
        *,
        symbol: str = "",
        limit: int = 8,
        enrich: bool = True,
    ) -> list[RawNewsItem]:
        """Symbol/keyword news for research sentiment — local then Bocha."""
        if not query and not symbol:
            return []
        focus = query or symbol
        items = await self._fetch_akshare_symbol(focus, limit)
        if _is_thin(items, limit):
            web = await self._fetch_web_search(
                limit,
                query=f"{focus} A股 新闻",
                freshness="oneWeek",
            )
            items = _dedupe_items([*items, *web])
        sliced = items[:limit]
        if enrich:
            return await self._enrich_excerpts(sliced)
        return sliced

    async def _fetch_market_flash(self, limit: int) -> list[RawNewsItem]:
        """Parallel CLS / THS / Sina / EM global flash feeds."""
        batches = await asyncio.gather(
            self._fetch_flash_source("cls", limit),
            self._fetch_flash_source("ths", limit),
            self._fetch_flash_source("sina", limit),
            self._fetch_flash_source("em", limit),
            return_exceptions=True,
        )
        items: list[RawNewsItem] = []
        for batch in batches:
            if isinstance(batch, list):
                items.extend(batch)
        return _dedupe_items(items)[:limit]

    async def _fetch_flash_source(self, kind: str, limit: int) -> list[RawNewsItem]:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_fetch_flash_sync_bounded, kind, limit),
                timeout=_AKSHARE_NEWS_TIMEOUT_SEC,
            )
        except TimeoutError:
            logger.warning("Flash news timed out for %s", kind)
            return []
        except Exception as exc:
            logger.warning("Flash news failed for %s: %s", kind, exc)
            return []

    async def _fetch_akshare_market(self, limit: int) -> list[RawNewsItem]:
        return await self._fetch_market_flash(limit)

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

    async def _fetch_web_search(
        self,
        limit: int,
        *,
        query: str = "A股 最新新闻 财经",
        freshness: str = "oneDay",
    ) -> list[RawNewsItem]:
        """博查 AI 联网搜索：本地源偏空时用符号/主题感知 query。"""
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
                "query": query,
                "freshness": freshness,
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
                published_at = (
                    _parse_datetime(row.get("datePublished"))
                    if row.get("datePublished")
                    else datetime.now(UTC)
                )
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

    async def _enrich_excerpts(
        self,
        items: list[RawNewsItem],
        *,
        budget: int = _ENRICH_LIMIT,
    ) -> list[RawNewsItem]:
        """Fetch short body excerpts for the top URL-bearing items."""
        if not items or budget <= 0:
            return items
        enriched: list[RawNewsItem] = []
        fetch_budget = budget
        for item in items:
            if fetch_budget <= 0 or not item.url or len(item.content) >= 200:
                enriched.append(item)
                continue
            excerpt = await fetch_url_excerpt(item.url, max_chars=500)
            fetch_budget -= 1
            if excerpt and len(excerpt) > len(item.content):
                enriched.append(
                    RawNewsItem(
                        title=item.title,
                        content=excerpt[:500],
                        source=item.source,
                        published_at=item.published_at,
                        url=item.url,
                    )
                )
            else:
                enriched.append(item)
        return enriched


def _is_thin(items: list[RawNewsItem], limit: int) -> bool:
    return len(items) < max(3, limit // 4)


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
            with CurlSession(impersonate="chrome") as s:
                resp = s.get(
                    "https://search-api-web.eastmoney.com/search/jsonp",
                    params=params,
                    headers=headers,
                    timeout=8.0,
                )
        else:
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


def _fetch_flash_sync_bounded(kind: str, limit: int, *, keyword: str = "") -> list[RawNewsItem]:
    """Hard-cap sync AkShare flash using a daemon thread so timeouts cannot pin the process."""
    import queue
    import threading

    result_q: queue.Queue[list[RawNewsItem] | BaseException] = queue.Queue(maxsize=1)

    def _worker() -> None:
        try:
            result_q.put(_fetch_flash_sync(kind, limit, keyword=keyword))
        except BaseException as exc:  # noqa: BLE001 — surface to waiter
            result_q.put(exc)

    thread = threading.Thread(target=_worker, name=f"flash-{kind}", daemon=True)
    thread.start()
    try:
        payload = result_q.get(timeout=_AKSHARE_NEWS_TIMEOUT_SEC - 0.5)
    except queue.Empty:
        logger.warning("Flash news hard-timeout for %s", kind)
        return []
    if isinstance(payload, BaseException):
        logger.warning("Flash news failed for %s: %s", kind, payload)
        return []
    return payload


def _fetch_flash_sync(kind: str, limit: int, *, keyword: str = "") -> list[RawNewsItem]:
    """Pull one global flash feed. kind: cls | ths | sina | em."""
    fetchers = {
        "cls": ("财联社", getattr(ak, "stock_info_global_cls", None)),
        "ths": ("同花顺", getattr(ak, "stock_info_global_ths", None)),
        "sina": ("新浪", getattr(ak, "stock_info_global_sina", None)),
        "em": ("东方财富全球", getattr(ak, "stock_info_global_em", None)),
    }
    label, fn = fetchers.get(kind, ("未知", None))
    if fn is None:
        return []
    try:
        df = fn()
    except Exception as exc:
        logger.warning("AkShare flash %s failed: %s", kind, exc)
        return []
    if df is None or getattr(df, "empty", True):
        return []

    items: list[RawNewsItem] = []
    for _, row in df.iterrows():
        title = str(
            row.get("标题") or row.get("title") or row.get("内容") or row.get("新闻标题") or ""
        ).strip()
        if not title:
            continue
        if keyword and keyword not in ("全部", "") and keyword not in title:
            continue
        summary = str(row.get("摘要") or row.get("内容") or row.get("新闻内容") or "").strip()
        url = str(row.get("链接") or row.get("url") or row.get("新闻链接") or "").strip()
        published_at = _parse_datetime(row.get("发布时间") or row.get("时间") or row.get("date"))
        items.append(
            RawNewsItem(
                title=title,
                content=(summary or title)[:500],
                source=label,
                published_at=published_at,
                url=url,
            )
        )
        if len(items) >= limit:
            break
    return items


def _fetch_em_global_news_sync(keyword: str, limit: int) -> list[RawNewsItem]:
    return _fetch_flash_sync_bounded("em", limit, keyword=keyword)


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
    # Prefer higher-authority sources when titles collide (CLS > EM > THS/Sina).
    authority = {"财联社": 3, "东方财富全球": 2, "东方财富": 2, "同花顺": 1, "新浪": 1}
    best: dict[str, RawNewsItem] = {}
    order: list[str] = []
    for item in items:
        key = item.title.strip()
        if not key:
            continue
        existing = best.get(key)
        if existing is None:
            best[key] = item
            order.append(key)
            continue
        if authority.get(item.source, 0) > authority.get(existing.source, 0):
            best[key] = item
    return [best[k] for k in order]
