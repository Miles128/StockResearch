"""Kimi Wind 深度数据 provider(公告/研报摘要,经 kimi CLI)。"""

from __future__ import annotations

import logging

from stockresearch.data.providers.kimi_cli import KimiCliClient, KimiCliError
from stockresearch.services.provider_cache_policy import get_or_set_cached_dict, provider_ttl

logger = logging.getLogger(__name__)

WIND_CACHE_KEY = "kimi:wind:daily_digest"

_WIND_PROMPT = """请整理今日 A 股市场重要公告与券商研报摘要,输出 JSON,schema 如下:
{
  "as_of": "数据日期 YYYY-MM-DD",
  "announcements": [{"title": "公告标题", "summary": "一句话摘要", "symbols": ["相关股票代码"]}],
  "research_reports": [{"title": "研报标题", "org": "券商", "rating": "评级",
                        "summary": "核心观点一句话"}]
}
announcements 取全市场最重要的 5-8 条;research_reports 取 3-5 条。"""


class KimiWindProvider:
    """Wind 深度数据(公告/研报)。失败返回 {},不抛异常、不写缓存。"""

    def __init__(self, client: KimiCliClient | None = None) -> None:
        self._client = client or KimiCliClient()

    async def get_daily_digest(self, *, refresh: bool = False) -> dict[str, object]:
        if refresh:
            return await self._fetch_and_store()
        return await get_or_set_cached_dict(WIND_CACHE_KEY, provider_ttl("kimi_wind"), self._fetch)

    async def _fetch(self) -> dict[str, object]:
        try:
            result = await self._client.query_json(_WIND_PROMPT)
        except KimiCliError as exc:
            logger.warning("Kimi Wind 数据获取失败: %s", exc)
            return {}
        payload = result.payload
        payload.setdefault("source", "kimi")
        return payload

    async def _fetch_and_store(self) -> dict[str, object]:
        from stockresearch.services.sqlite_cache import set_sqlite_cached

        payload = await self._fetch()
        if payload:
            set_sqlite_cached(WIND_CACHE_KEY, payload, provider_ttl("kimi_wind"))
        return payload
