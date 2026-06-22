"""Balance checker: ensure output presents balanced perspectives.

Checks final output for:
1. Negative signal dominance (>60% negative → auto-append balancing info)
2. Single-dimension views (→ auto-append cross-dimension caveat)
3. Predictive statements without uncertainty disclaimer

This runs after neutral_guard but before glossary marking.
"""

from __future__ import annotations

import re

# Signals that indicate negative/directional stance
_NEGATIVE_SIGNALS = re.compile(
    r"下跌|跌|跌停|亏损|风险|回撤|暴跌|崩盘|看空|偏空|bearish|卖出|减仓|止损|压力|弱势|恶化|流出"
)
_POSITIVE_SIGNALS = re.compile(
    r"上涨|涨|涨停|盈利|机会|利好|看多|偏多|bullish|买入|加仓|支撑|强势|改善|流入"
)
_PREDICTIVE_PATTERNS = re.compile(
    r"预计|预期|将会|可能达到|有望|或将|或迎"
)
_DIMENSION_LABELS = re.compile(r"(基本面|技术面|情绪面|筹码面|宏观|行业)")


def check_balance(text: str) -> str:
    """Check and balance the output text.

    Returns the text with balancing appendages if needed.
    """
    neg_count = len(_NEGATIVE_SIGNALS.findall(text))
    pos_count = len(_POSITIVE_SIGNALS.findall(text))
    total = neg_count + pos_count

    appendages: list[str] = []

    # 1. Negative dominance check
    if total > 0 and neg_count / total > 0.6:
        appendages.append(
            "同时注意到，市场环境存在多空交织因素，单一方向判断需审慎。"
        )

    # 2. Single-dimension check
    dimensions_found = set(_DIMENSION_LABELS.findall(text))
    if len(dimensions_found) == 1:
        dim = next(iter(dimensions_found))
        appendages.append(
            f"以上仅为{dim}视角，其他维度（如{'、'.join(d for d in ['基本面', '技术面', '情绪面', '筹码面'] if d != dim)[:2]}）"
            f"可能有不同结论。"
        )

    # 3. Predictive statements without disclaimer
    if _PREDICTIVE_PATTERNS.search(text) and "不保证" not in text and "不代表" not in text:
        appendages.append("以上基于历史数据推演，不保证未来走势。")

    if not appendages:
        return text

    return text.rstrip() + "\n\n" + " ".join(appendages)
