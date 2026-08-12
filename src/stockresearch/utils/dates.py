"""通用日期解析辅助——消除跨模块的 _parse_date 重复实现。

统一行为：接受 datetime/date/str（含 %Y-%m-%d[ %H:%M:%S]、%Y/%m/%d、%Y%m%d），
解析失败返回 None。各调用方按需取 .date() 或时区。
"""

from __future__ import annotations

from datetime import UTC, date, datetime


def parse_date_any(value: object) -> datetime | None:
    """宽松解析为 aware datetime；失败返回 None。"""
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    if not isinstance(value, str):
        return None
    text = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def parse_date_str(value: str) -> date | None:
    """从字符串解析为 date（%Y-%m-%d / %Y/%m/%d / %Y%m%d）；失败返回 None。"""
    text = (value or "").strip()[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None
