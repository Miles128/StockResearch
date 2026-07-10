"""轻量持仓摘要构建，仅从 DB 模型计算，不拉实时行情。"""

from __future__ import annotations

from collections import Counter
from typing import Any

from stockresearch.db.models import Holding


def build_portfolio_brief(holdings: list[Holding]) -> dict[str, Any]:
    """构建持仓摘要，供 tool call 返回给 AI。

    仅读取 DB 字段（symbol/name/cost_price/quantity/sector/buy_date），
    不拉取实时行情，避免上下文污染。
    """
    if not holdings:
        return {
            "total_cost": 0.0,
            "total_quantity": 0,
            "count": 0,
            "holdings": [],
            "sectors": [],
        }

    total_cost = sum(h.float_cost_price * h.quantity for h in holdings)
    total_quantity = sum(h.quantity for h in holdings)

    sector_counts: Counter[str] = Counter()
    for h in holdings:
        sector_counts[h.sector or "未知"] += 1
    sectors = [
        {"name": name, "count": count}
        for name, count in sector_counts.most_common()
    ]

    holdings_list = [
        {
            "symbol": h.symbol,
            "name": h.name,
            "cost_price": h.float_cost_price,
            "quantity": h.quantity,
            "sector": h.sector or "未知",
            "buy_date": h.buy_date.isoformat() if h.buy_date else None,
        }
        for h in holdings
    ]

    return {
        "total_cost": total_cost,
        "total_quantity": total_quantity,
        "count": len(holdings),
        "holdings": holdings_list,
        "sectors": sectors,
    }
