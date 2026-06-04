"""Portfolio holding P&L and annualized return from cost and live/close price."""

from datetime import date


def profit_amount(cost_price: float, quantity: int, price: float) -> float:
    return round((price - cost_price) * quantity, 2)


def profit_pct(cost_price: float, price: float) -> float:
    if cost_price <= 0:
        return 0.0
    return round((price / cost_price - 1.0) * 100.0, 2)


def annualized_return_pct(cost_price: float, price: float, buy_date: date | None) -> float | None:
    if buy_date is None or cost_price <= 0 or price <= 0:
        return None
    days = (date.today() - buy_date).days
    if days < 1:
        days = 1
    total_factor = price / cost_price
    return round((total_factor ** (365.0 / days) - 1.0) * 100.0, 2)
