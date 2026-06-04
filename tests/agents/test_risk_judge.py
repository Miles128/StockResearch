"""Judge verdict parsing tests."""

from stockresearch.agents.risk.judge import ensure_all_holdings_covered, parse_judge
from stockresearch.agents.risk.stream import _parse_judge
from stockresearch.core.constants import SEVERITY_RED
from stockresearch.core.schemas import RiskAlertOut
from stockresearch.db.models import Holding


def _holding(symbol: str, name: str) -> Holding:
    return Holding(
        id=1,
        user_id=1,
        symbol=symbol,
        name=name,
        cost_price=100.0,
        quantity=100,
        sector="测试",
    )


def test_parse_judge_json_covers_all_holdings() -> None:
    holdings = [
        _holding("300750", "宁德时代"),
        _holding("600519", "贵州茅台"),
        _holding("000001", "平安银行"),
        _holding("601318", "中国平安"),
    ]
    raw = (
        '{"analysis_process":"1. 看告警\\n2. 看辩论\\n3. 逐股结论",'
        '"risk_level":"高","position_action":"减仓",'
        '"holding_actions":[{"symbol":"300750","name":"宁德时代","action":"减仓",'
        '"reason":"回撤过大","priority":"高"}],'
        '"summary":"优先处理回撤标的","reason":"组合仍有联动风险","divergence":"分歧中等"}'
    )
    verdict = parse_judge(raw, [], holdings)
    assert len(verdict.holding_actions) == 4
    assert verdict.holding_actions[0].symbol == "300750"
    assert verdict.holding_actions[0].action == "减仓"
    assert any(item.symbol == "600519" for item in verdict.holding_actions)


def test_parse_judge_fallback_from_alerts() -> None:
    holdings = [_holding("300750", "宁德时代")]
    alerts = [
        RiskAlertOut(
            rule_id="stop_loss_red",
            severity=SEVERITY_RED,
            symbol="300750",
            message="亏损过大",
            human_message="",
        )
    ]
    verdict = _parse_judge("无法解析", alerts, holdings)
    assert verdict.position_action == "减仓"
    assert len(verdict.holding_actions) == 1
    assert verdict.holding_actions[0].action == "减仓"
    assert verdict.analysis_process


def test_ensure_all_holdings_covered_fills_missing() -> None:
    holdings = [
        _holding("300750", "宁德时代"),
        _holding("600519", "贵州茅台"),
    ]
    covered = ensure_all_holdings_covered(holdings, [], [])
    assert len(covered) == 2
    symbols = {item.symbol for item in covered}
    assert symbols == {"300750", "600519"}
