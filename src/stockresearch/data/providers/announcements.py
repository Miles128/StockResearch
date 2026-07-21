"""巨潮信息网（cninfo）公告 provider — 通过 AkShare 接口拉取上市公司公告。

数据源：巨潮资讯网 http://www.cninfo.com.cn
AkShare 接口：stock_zh_a_disclosure_report_cninfo
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import akshare as ak  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

_CNINFO_TIMEOUT_SEC = 12.0


@dataclass(frozen=True)
class AnnouncementItem:
    """巨潮公告条目。"""

    title: str
    announcement_type: str  # 公告类型，如"年报"、"重大事项"、"减持"等
    announcement_time: datetime
    symbol: str
    name: str
    url: str = ""


@dataclass(frozen=True)
class AnnouncementFetchResult:
    items: list[AnnouncementItem]
    source_failed: bool = False


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


def fetch_cninfo_announcements_sync(
    symbol: str,
    name: str = "",
    *,
    category: str = "",
    days: int = 30,
    limit: int = 20,
) -> AnnouncementFetchResult:
    """同步拉取指定股票最近 N 天的巨潮公告。

    Empty items + source_failed=False means the source answered with no rows.
    source_failed=True means the provider call itself failed.
    """
    end_date = datetime.now(UTC).strftime("%Y%m%d")
    start_date = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y%m%d")
    try:
        df = ak.stock_zh_a_disclosure_report_cninfo(
            symbol=symbol,
            market=_market_code(symbol),
            category=category,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as exc:
        logger.warning("AkShare cninfo announcements failed for %s: %s", symbol, exc)
        return AnnouncementFetchResult(items=[], source_failed=True)

    if df is None or df.empty:
        return AnnouncementFetchResult(items=[], source_failed=False)

    items: list[AnnouncementItem] = []
    for _, row in df.head(limit).iterrows():
        title = str(row.get("公告标题", "")).strip()
        if not title:
            continue
        ann_type = str(row.get("公告类型", "")).strip()
        ann_time = _parse_datetime(row.get("公告时间", row.get("公告日期", "")))
        url = str(row.get("公告链接", row.get("adjunctUrl", ""))).strip()
        items.append(
            AnnouncementItem(
                title=title,
                announcement_type=ann_type,
                announcement_time=ann_time,
                symbol=symbol,
                name=name,
                url=url,
            )
        )
    return AnnouncementFetchResult(items=items, source_failed=False)


def _market_code(symbol: str) -> str:
    """AkShare cninfo 接口要求的市场代码：沪深京 -> sz/sh/bj。"""
    if symbol.startswith("6"):
        return "sh"
    if symbol.startswith(("4", "8")):
        return "bj"
    return "sz"


class AnnouncementProvider:
    """异步公告 provider，封装 cninfo 拉取逻辑。"""

    async def fetch_announcements_result(
        self,
        symbol: str,
        name: str = "",
        *,
        category: str = "",
        days: int = 30,
        limit: int = 20,
    ) -> AnnouncementFetchResult:
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(
                        fetch_cninfo_announcements_sync,
                        symbol,
                        name,
                        category=category,
                        days=days,
                        limit=limit,
                    ),
                    timeout=_CNINFO_TIMEOUT_SEC,
                )
            except TimeoutError as exc:
                last_exc = exc
                logger.warning(
                    "Cninfo announcements timed out for %s (attempt %d)",
                    symbol,
                    attempt + 1,
                )
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Cninfo announcements failed for %s (attempt %d): %s",
                    symbol,
                    attempt + 1,
                    exc,
                )
            if attempt == 0:
                await asyncio.sleep(0.4)
        if last_exc:
            return AnnouncementFetchResult(items=[], source_failed=True)
        return AnnouncementFetchResult(items=[], source_failed=True)

    async def fetch_announcements(
        self,
        symbol: str,
        name: str = "",
        *,
        category: str = "",
        days: int = 30,
        limit: int = 20,
    ) -> list[AnnouncementItem]:
        result = await self.fetch_announcements_result(
            symbol, name, category=category, days=days, limit=limit
        )
        return list(result.items)

    async def fetch_latest_for_symbols(
        self,
        symbol_pairs: list[tuple[str, str]],
        *,
        category: str = "",
        days: int = 30,
        per_symbol_limit: int = 5,
    ) -> list[AnnouncementItem]:
        """批量并行拉取多只股票的公告，按时间倒序合并去重。"""
        tasks = [
            asyncio.create_task(
                self.fetch_announcements(
                    symbol,
                    name,
                    category=category,
                    days=days,
                    limit=per_symbol_limit,
                )
            )
            for symbol, name in symbol_pairs[:10]
        ]
        items: list[AnnouncementItem] = []
        if tasks:
            batches = await asyncio.gather(*tasks, return_exceptions=True)
            for batch in batches:
                if isinstance(batch, list):
                    items.extend(batch)
        items.sort(key=lambda x: x.announcement_time, reverse=True)
        return items
