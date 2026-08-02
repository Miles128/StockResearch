"""Kimi 宏观与行业数据 provider(World Bank / IMF / Gildata 源,经 kimi CLI)。"""

from __future__ import annotations

import logging

from stockresearch.data.providers.kimi_cli import KimiCliClient, KimiCliError
from stockresearch.services.provider_cache_policy import get_or_set_cached_dict, provider_ttl

logger = logging.getLogger(__name__)

MACRO_CACHE_KEY = "kimi:macro:cn_daily"

_MACRO_PROMPT = """请查询中国最新一期宏观经济数据并整理为 JSON,schema 如下:
{
  "as_of": "数据日期 YYYY-MM-DD",
  "indicators": [{"name": "指标名(如 CPI 同比/PPI 同比/制造业 PMI/LPR 1年期/GDP 同比/社融存量同比)",
                  "value": "数值带单位", "period": "数据期", "trend": "up|down|flat",
                  "comment": "一句话解读"}],
  "industry_highlights": [{"industry": "行业名", "summary": "近期行业动态一句话"}]
}
indicators 覆盖 CPI、PPI、PMI、LPR、GDP、社融;industry_highlights 给 3-5 条。"""


class KimiMacroProvider:
    """宏观与行业数据。失败返回 {},不抛异常、不写缓存。"""

    def __init__(self, client: KimiCliClient | None = None) -> None:
        self._client = client or KimiCliClient()

    async def get_macro_snapshot(self, *, refresh: bool = False) -> dict[str, object]:
        if refresh:
            return await self._fetch_and_store()
        return await get_or_set_cached_dict(
            MACRO_CACHE_KEY, provider_ttl("kimi_macro"), self._fetch
        )

    async def _fetch(self) -> dict[str, object]:
        try:
            result = await self._client.query_json(_MACRO_PROMPT)
        except KimiCliError as exc:
            logger.warning("Kimi 宏观数据获取失败: %s", exc)
            return {}
        payload = result.payload
        # 空壳 payload(缺关键字段)视为无数据,不写缓存
        if not (payload.get("indicators") or payload.get("industry_highlights")):
            return {}
        payload.setdefault("source", "kimi")
        return payload

    async def _fetch_and_store(self) -> dict[str, object]:
        from stockresearch.services.sqlite_cache import set_sqlite_cached

        payload = await self._fetch()
        if payload:
            set_sqlite_cached(MACRO_CACHE_KEY, payload, provider_ttl("kimi_macro"))
        return payload
