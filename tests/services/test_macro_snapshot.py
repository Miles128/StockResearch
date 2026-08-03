"""Macro snapshot formatting tests."""

from stockresearch.data.providers.kimi_macro import MACRO_CACHE_KEY
from stockresearch.services.macro_snapshot import format_macro_snapshot
from stockresearch.services.sqlite_cache import set_sqlite_cached

_MACRO_PAYLOAD = {
    "as_of": "2026-08-01",
    "indicators": [
        {
            "name": "CPI 同比",
            "value": "0.4%",
            "period": "2026-06",
            "trend": "up",
            "comment": "温和回升",
        },
        {
            "name": "制造业 PMI",
            "value": "49.7",
            "period": "2026-07",
            "trend": "flat",
            "comment": "",
        },
    ],
    "industry_highlights": [
        {"industry": "电力", "summary": "用电需求走高"},
    ],
    "source": "kimi",
}


def test_format_macro_snapshot_without_cache() -> None:
    assert format_macro_snapshot() == ""


def test_format_macro_snapshot_with_cache() -> None:
    set_sqlite_cached(MACRO_CACHE_KEY, _MACRO_PAYLOAD, 86400)
    text = format_macro_snapshot(max_lines=None)
    assert "【宏观数据(Kimi, 2026-08-01)】" in text
    assert "CPI 同比: 0.4%(2026-06) 趋势:up温和回升" in text
    assert "行业·电力: 用电需求走高" in text


def test_format_macro_snapshot_caps_lines() -> None:
    payload = {
        "as_of": "2026-08-01",
        "indicators": [
            {"name": f"指标{i}", "value": "1", "period": "2026-07", "trend": "flat", "comment": ""}
            for i in range(12)
        ],
        "source": "kimi",
    }
    set_sqlite_cached(MACRO_CACHE_KEY, payload, 86400)
    text = format_macro_snapshot()
    # 默认上限 8 行内容 + 1 行标题
    assert len(text.splitlines()) == 9


def test_format_macro_snapshot_empty_payload() -> None:
    set_sqlite_cached(MACRO_CACHE_KEY, {"as_of": "2026-08-01"}, 86400)
    assert format_macro_snapshot() == ""
