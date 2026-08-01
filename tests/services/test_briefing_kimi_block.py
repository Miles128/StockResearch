from stockresearch.data.providers.kimi_macro import MACRO_CACHE_KEY
from stockresearch.data.providers.kimi_wind import WIND_CACHE_KEY
from stockresearch.services.briefing import _collect_kimi_block
from stockresearch.services.sqlite_cache import set_sqlite_cached


def test_kimi_block_empty_when_no_cache() -> None:
    assert _collect_kimi_block() == ""


def test_kimi_block_formats_macro_and_wind() -> None:
    set_sqlite_cached(
        MACRO_CACHE_KEY,
        {"as_of": "2026-08-01",
         "indicators": [{"name": "CPI 同比", "value": "0.3%", "period": "2026-06",
                         "trend": "flat", "comment": "温和"}],
         "industry_highlights": [{"industry": "新能源", "summary": "装机高增"}]},
        3600,
    )
    set_sqlite_cached(
        WIND_CACHE_KEY,
        {"as_of": "2026-08-01",
         "announcements": [{"title": "某公司回购", "summary": "拟回购 2%", "symbols": ["600519"]}],
         "research_reports": [{"title": "白酒深度", "org": "中信证券", "rating": "买入",
                               "summary": "需求回暖"}]},
        3600,
    )
    block = _collect_kimi_block()
    assert "CPI 同比" in block and "0.3%" in block
    assert "新能源" in block
    assert "某公司回购" in block
    assert "白酒深度" in block
