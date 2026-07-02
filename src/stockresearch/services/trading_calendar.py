"""A-share trading calendar validation."""

import logging
from datetime import date, datetime
from functools import lru_cache

import akshare as ak

from stockresearch.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_trading_days() -> frozenset[date]:
    df = ak.tool_trade_date_hist_sina()
    col = "trade_date"
    days: set[date] = set()
    for value in df[col].tolist():
        if isinstance(value, date):
            days.add(value)
            continue
        if isinstance(value, datetime):
            days.add(value.date())
            continue
        text = str(value)[:10]
        days.add(date.fromisoformat(text))
    return frozenset(days)


def is_a_share_trading_day(value: date) -> bool:
    return value in _load_trading_days()


def validate_buy_date(buy_date: date | None) -> None:
    """Raise ValidationError when buy_date is not an A-share session day."""
    if buy_date is None:
        return
    today = date.today()
    if buy_date > today:
        raise ValidationError("买入日期不能晚于今天")
    try:
        if not is_a_share_trading_day(buy_date):
            raise ValidationError(
                f"{buy_date.isoformat()} 不是 A 股交易日（当日无开盘），请重新选择"
            )
    except ValidationError:
        raise
    except Exception as exc:
        logger.warning("Trading calendar check failed: %s", exc)
        if buy_date.weekday() >= 5:
            raise ValidationError(
                f"{buy_date.isoformat()} 为周末，不是交易日，请重新选择"
            ) from exc
        from stockresearch.core.config import get_settings

        if get_settings().use_mock_market_data:
            return
        raise ValidationError("无法校验交易日历，请稍后重试") from exc
