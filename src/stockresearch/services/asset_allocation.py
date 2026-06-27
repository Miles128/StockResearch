"""投顾模式专属：资产配置参考服务。

根据用户的风险承受能力等级 + 现金流情况，给出股/债/现金的参考配置比例。

合规边界（PRD §8）：
- 这是「教育参考」而非「建仓指令」
- 不输出买入/卖出/目标价
- 用「参考配置」「常见比例」等措辞，不用「你应该」
- 附带免责声明
"""

import logging

from stockresearch.agents.voice import AGENT_VOICE
from stockresearch.core.schemas import AssetAllocationOut
from stockresearch.utils.llm import LLMClient, get_llm_client

logger = logging.getLogger(__name__)

# ── 风险等级 → 参考配置比例 ──
# 这是常见的资产配置教育参考，不是建仓指令。
ALLOCATION_PRESETS: dict[str, dict[str, float]] = {
    "conservative": {"股票": 0.30, "债券": 0.50, "现金": 0.20},
    "moderate": {"股票": 0.50, "债券": 0.35, "现金": 0.15},
    "aggressive": {"股票": 0.70, "债券": 0.20, "现金": 0.10},
}

RISK_LABELS: dict[str, str] = {
    "conservative": "保守",
    "moderate": "稳健",
    "aggressive": "进取",
}

# 应急资金建议月数（按风险等级）
EMERGENCY_FUND_MONTHS: dict[str, tuple[int, int]] = {
    "conservative": (6, 12),
    "moderate": (3, 6),
    "aggressive": (3, 6),
}

# 各等级的典型最大回撤参考（用于现金流换算）
TYPICAL_MAX_DRAWDOWN: dict[str, float] = {
    "conservative": 0.10,
    "moderate": 0.20,
    "aggressive": 0.35,
}


def _build_cash_flow_impact(risk_tolerance: str, monthly_income: float) -> str:
    """把风险换算成现金流感受：月收入的 X% / 相当于 X 个月收入。"""
    drawdown = TYPICAL_MAX_DRAWDOWN.get(risk_tolerance, 0.20)
    # 假设投资资金约为 12 个月收入（教育假设，非真实数据）
    assumed_capital = monthly_income * 12
    potential_loss = assumed_capital * drawdown
    loss_months = potential_loss / monthly_income
    loss_pct_of_income = (potential_loss / monthly_income) * 100

    return (
        f"假设你的投资资金约为 12 个月收入（¥{assumed_capital:,.0f}），"
        f"在{RISK_LABELS[risk_tolerance]}配置下，"
        f"极端行情可能浮亏约 ¥{potential_loss:,.0f}，"
        f"相当于 {loss_months:.1f} 个月收入（月收入的 {loss_pct_of_income:.0f}%）。"
        f"这个数字帮你直观感受风险等级的差异。"
    )


def _build_emergency_fund_note(risk_tolerance: str, monthly_income: float) -> str:
    """应急资金建议：在投资前先留足生活应急金。"""
    low, high = EMERGENCY_FUND_MONTHS.get(risk_tolerance, (3, 6))
    low_amount = monthly_income * low
    high_amount = monthly_income * high
    return (
        f"投资前建议先留足 {low}-{high} 个月生活费的应急资金"
        f"（约 ¥{low_amount:,.0f}-¥{high_amount:,.0f}），"
        f"放在活期或货币基金里，随时能取。"
        f"这笔钱不投资，专门应对失业、生病等突发情况。"
    )


async def _llm_rationale(
    llm: LLMClient,
    risk_tolerance: str,
    allocation: dict[str, float],
    monthly_income: float | None,
) -> str:
    """用 LLM 生成大白话解释（投顾模式 friendly）。"""
    risk_label = RISK_LABELS[risk_tolerance]
    alloc_desc = "、".join(f"{k} {int(v * 100)}%" for k, v in allocation.items())

    system = (
        f"你是个人投顾助手。{AGENT_VOICE} 用大白话解释为什么这样的资产配置适合用户。"
        "称呼「您」。不制造恐慌，不要建议买卖，不要给具体股票。"
        "这是教育参考，不是投资指令。"
    )
    user_parts = [
        f"用户风险等级：{risk_label}",
        f"参考配置：{alloc_desc}",
    ]
    if monthly_income and monthly_income > 0:
        user_parts.append(f"用户月收入：¥{monthly_income:,.0f}")
    user = "\n".join(user_parts)

    return (await llm.complete(system, user)).strip()


def _fallback_rationale(risk_tolerance: str, allocation: dict[str, float]) -> str:
    """LLM 不可用时的规则兜底解释。"""
    risk_label = RISK_LABELS[risk_tolerance]
    stock_pct = int(allocation.get("股票", 0) * 100)
    bond_pct = int(allocation.get("债券", 0) * 100)
    cash_pct = int(allocation.get("现金", 0) * 100)

    if risk_tolerance == "conservative":
        return (
            f"你是「{risk_label}」型，参考配置是股票 {stock_pct}%、债券 {bond_pct}%、现金 {cash_pct}%。"
            f"股票比例低，因为你不愿承受大波动；债券和现金比例高，保证稳定性。"
            f"适合把保本放在第一位的人。"
        )
    if risk_tolerance == "aggressive":
        return (
            f"你是「{risk_label}」型，参考配置是股票 {stock_pct}%、债券 {bond_pct}%、现金 {cash_pct}%。"
            f"股票比例高，因为你能承受较大波动去追求更高收益；"
            f"债券和现金留少量，作为机动资金。适合追求增长、能扛住回撤的人。"
        )
    return (
        f"你是「{risk_label}」型，参考配置是股票 {stock_pct}%、债券 {bond_pct}%、现金 {cash_pct}%。"
        f"股债各占一半左右，兼顾增长和稳定。"
        f"适合想增值但不愿承受太大波动的人。"
    )


async def build_asset_allocation(
    risk_tolerance: str,
    monthly_income: float | None = None,
    llm: LLMClient | None = None,
) -> AssetAllocationOut:
    """构建资产配置参考。"""
    allocation = ALLOCATION_PRESETS.get(risk_tolerance, ALLOCATION_PRESETS["moderate"])
    risk_label = RISK_LABELS.get(risk_tolerance, "稳健")

    # 现金流分析（有月收入才生成）
    cash_flow_impact: str | None = None
    emergency_fund_note: str | None = None
    if monthly_income and monthly_income > 0:
        cash_flow_impact = _build_cash_flow_impact(risk_tolerance, monthly_income)
        emergency_fund_note = _build_emergency_fund_note(risk_tolerance, monthly_income)

    # LLM 大白话解释（有兜底）
    client = llm or get_llm_client()
    try:
        rationale = await _llm_rationale(client, risk_tolerance, allocation, monthly_income)
        if not rationale:
            rationale = _fallback_rationale(risk_tolerance, allocation)
    except Exception:
        logger.warning("LLM rationale failed, using fallback")
        rationale = _fallback_rationale(risk_tolerance, allocation)

    return AssetAllocationOut(
        risk_tolerance=risk_tolerance,  # type: ignore[arg-type]
        risk_label=risk_label,
        allocation=allocation,
        rationale=rationale,
        cash_flow_impact=cash_flow_impact,
        emergency_fund_note=emergency_fund_note,
    )
