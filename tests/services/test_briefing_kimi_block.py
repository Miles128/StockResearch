from stockresearch.data.providers.kimi_macro import MACRO_CACHE_KEY
from stockresearch.data.providers.kimi_wind import WIND_CACHE_KEY
from stockresearch.services.briefing import _collect_kimi_block, _fallback_sections
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
    assert "趋势:flat" in block
    assert "新能源" in block
    assert "某公司回购" in block
    assert "白酒深度" in block


def test_fallback_sections_include_kimi_block_when_present() -> None:
    summary, sections = _fallback_sections(
        kind="intraday",
        holdings_block="【持仓表现】\n- 示例",
        holding_news=[],
        sector_news=[],
        market_news=[],
        market_block="【大盘概况】\n指数数据暂不可用",
        alerts=[],
        kimi_block="【宏观数据(Kimi, 2026-08-01)】\n- CPI 同比: 0.3%(2026-06) 趋势:flat温和",
    )
    titles = [s.title for s in sections]
    assert "宏观与市场动态(Kimi)" in titles
    kimi_section = sections[titles.index("宏观与市场动态(Kimi)")]
    assert "CPI 同比" in kimi_section.content


def test_fallback_sections_omit_kimi_block_when_empty() -> None:
    _, sections = _fallback_sections(
        kind="intraday",
        holdings_block="【持仓表现】\n- 示例",
        holding_news=[],
        sector_news=[],
        market_news=[],
        market_block="【大盘概况】\n指数数据暂不可用",
        alerts=[],
        kimi_block="",
    )
    assert "宏观与市场动态(Kimi)" not in [s.title for s in sections]
