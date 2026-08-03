"""Gap refill classification and cache eviction tests."""

from stockresearch.db.session import init_db
from stockresearch.services.cache import CacheService
from stockresearch.services.refill_gaps import classify_gaps, evict_gap_caches
from stockresearch.services.sqlite_cache import get_sqlite_cached, set_sqlite_cached


def test_classify_gaps_maps_categories() -> None:
    gaps = [
        "公告仅标题",
        "财务序列不完整",
        "估值历史分位缺失",
        "个股新闻为空",
        "筹码数据不可用",
        "疑似停牌，行情可能陈旧",
    ]
    assert classify_gaps(gaps) == [
        "announcements",
        "financial",
        "news_sentiment",
        "chips",
        "quotes",
    ]


def test_classify_gaps_dedupes_and_ignores_unknown() -> None:
    assert classify_gaps(["公告仅标题", "公告缺失", "无法识别的缺口", ""]) == ["announcements"]
    assert classify_gaps(None) == []


def test_evict_gap_caches_scoped_to_symbol() -> None:
    cache = CacheService()
    cache.set("research:600519:standard", "{}")
    cache.set("research:000858:standard", "{}")
    cache.set("kline:600519:250:2026-08-01", "{}")

    evict_gap_caches("600519", ["financial"])

    assert cache.get("research:600519:standard") is None
    assert cache.get("kline:600519:250:2026-08-01") is None
    assert cache.get("research:000858:standard") is not None


def test_evict_gap_caches_sqlite_provider_entries() -> None:
    init_db()
    set_sqlite_cached("financials:unified:v1:600519", {"roe": 30.0}, ttl_seconds=3600)
    set_sqlite_cached("financials:unified:v1:000858", {"roe": 20.0}, ttl_seconds=3600)

    evict_gap_caches("600519", ["financial"])

    assert get_sqlite_cached("financials:unified:v1:600519") is None
    assert get_sqlite_cached("financials:unified:v1:000858") is not None
