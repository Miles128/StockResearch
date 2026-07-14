"""东方财富研报 provider — 通过 AkShare 拉取机构研报摘要。

数据源：东方财富网机构研报 https://data.eastmoney.com/report/
AkShare 接口：stock_research_report_em(symbol)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import akshare as ak  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

_REPORT_TIMEOUT_SEC = 12.0


@dataclass(frozen=True)
class ResearchReportItem:
    """东方财富机构研报条目。"""

    title: str
    institution: str  # 研究机构
    analyst: str  # 分析师
    rating: str  # 评级，如"买入"、"增持"、"中性"
    target_price: float | None  # 目标价（元）
    publish_date: datetime
    symbol: str
    name: str
    summary: str = ""


@dataclass(frozen=True)
class ResearchReportFetchResult:
    items: list[ResearchReportItem]
    source_failed: bool = False


def _parse_date(value: object) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(value, fmt)
                return dt.replace(tzinfo=UTC)
            except ValueError:
                continue
    return datetime.now(UTC)


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        s = str(value).strip().strip("-").strip()
        if not s:
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def fetch_research_reports_sync(
    symbol: str,
    name: str = "",
    *,
    limit: int = 20,
) -> ResearchReportFetchResult:
    """同步拉取指定股票最近的东方财富机构研报。"""
    try:
        df = ak.stock_research_report_em(symbol=symbol)
    except Exception as exc:
        logger.warning("AkShare research reports failed for %s: %s", symbol, exc)
        return ResearchReportFetchResult(items=[], source_failed=True)

    if df is None or df.empty:
        return ResearchReportFetchResult(items=[], source_failed=False)

    items: list[ResearchReportItem] = []
    for _, row in df.head(limit).iterrows():
        title = str(row.get("标题", row.get("研报标题", ""))).strip()
        if not title:
            continue
        institution = str(row.get("机构", row.get("研究机构", ""))).strip()
        analyst = str(row.get("研究员", row.get("分析师", ""))).strip()
        rating = str(row.get("评级", row.get("投资评级", ""))).strip()
        target_price = _safe_float(row.get("目标价", row.get("目标价格")))
        publish_date = _parse_date(row.get("日期", row.get("发布日期", "")))
        summary = str(row.get("摘要", row.get("研报摘要", ""))).strip()
        items.append(
            ResearchReportItem(
                title=title,
                institution=institution,
                analyst=analyst,
                rating=rating,
                target_price=target_price,
                publish_date=publish_date,
                symbol=symbol,
                name=name,
                summary=summary[:500],
            )
        )
    return ResearchReportFetchResult(items=items, source_failed=False)


class ResearchReportProvider:
    """异步研报 provider，封装东方财富研报拉取逻辑。"""

    async def fetch_reports_result(
        self,
        symbol: str,
        name: str = "",
        *,
        limit: int = 20,
    ) -> ResearchReportFetchResult:
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(
                        fetch_research_reports_sync,
                        symbol,
                        name,
                        limit=limit,
                    ),
                    timeout=_REPORT_TIMEOUT_SEC,
                )
            except TimeoutError as exc:
                last_exc = exc
                logger.warning(
                    "Eastmoney research reports timed out for %s (attempt %d)",
                    symbol,
                    attempt + 1,
                )
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Eastmoney research reports failed for %s (attempt %d): %s",
                    symbol,
                    attempt + 1,
                    exc,
                )
            if attempt == 0:
                await asyncio.sleep(0.4)
        if last_exc:
            return ResearchReportFetchResult(items=[], source_failed=True)
        return ResearchReportFetchResult(items=[], source_failed=True)

    async def fetch_reports(
        self,
        symbol: str,
        name: str = "",
        *,
        limit: int = 20,
    ) -> list[ResearchReportItem]:
        result = await self.fetch_reports_result(symbol, name, limit=limit)
        return list(result.items)

    async def fetch_latest_for_symbols(
        self,
        symbol_pairs: list[tuple[str, str]],
        *,
        per_symbol_limit: int = 5,
    ) -> list[ResearchReportItem]:
        """批量并行拉取多只股票的研报，按发布时间倒序合并。"""
        tasks = [
            asyncio.create_task(self.fetch_reports(symbol, name, limit=per_symbol_limit))
            for symbol, name in symbol_pairs[:10]
        ]
        items: list[ResearchReportItem] = []
        if tasks:
            batches = await asyncio.gather(*tasks, return_exceptions=True)
            for batch in batches:
                if isinstance(batch, list):
                    items.extend(batch)
        items.sort(key=lambda x: x.publish_date, reverse=True)
        return items
