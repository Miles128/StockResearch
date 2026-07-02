"""Tests for PRD §9.1 compliance language."""

from stockresearch.services.compliance_language import (
    HOLDING_NO_CHANGE,
    POSITION_BIAS_HIGH,
    POSITION_BIAS_LOW,
    POSITION_BIAS_NEUTRAL,
    contains_forbidden_position_language,
    normalize_position_action,
    scrub_forbidden_position_language,
)
from stockresearch.services.neutral_guard import apply_ban_filter, neutral_guard


class TestComplianceLanguage:
    def test_normalize_legacy_add(self):
        assert normalize_position_action("加仓") == POSITION_BIAS_LOW

    def test_normalize_legacy_reduce(self):
        assert normalize_position_action("减仓") == POSITION_BIAS_HIGH

    def test_normalize_legacy_hold(self):
        assert normalize_position_action("持有观望") == POSITION_BIAS_NEUTRAL

    def test_scrub_forbidden_terms(self):
        text = scrub_forbidden_position_language("组合倾向减仓，宁德时代持有观望")
        assert "减仓" not in text
        assert "持有观望" not in text
        assert POSITION_BIAS_HIGH in text
        assert POSITION_BIAS_NEUTRAL in text

    def test_contains_forbidden(self):
        assert contains_forbidden_position_language("建议加仓")
        assert not contains_forbidden_position_language("仓位偏高")

    def test_portfolio_fallback(self):
        assert normalize_position_action("", portfolio=True) == POSITION_BIAS_NEUTRAL

    def test_holding_fallback(self):
        assert normalize_position_action("unknown", portfolio=False) == HOLDING_NO_CHANGE


class TestNeutralGuardCompliance:
    def test_allows_suggested_buy(self):
        result = apply_ban_filter("建议买入招商银行")
        assert "建议买入" in result

    def test_allows_suggested_sell(self):
        result = apply_ban_filter("建议卖出部分仓位")
        assert "建议卖出" in result

    def test_bans_reduce_term(self):
        result = apply_ban_filter("组合倾向减仓")
        assert "减仓" not in result
        assert "仓位偏高" in result

    def test_bans_hold_watch_term(self):
        result = apply_ban_filter("当前持有观望")
        assert "持有观望" not in result

    def test_neutral_guard_preserves_buy_suggestion(self):
        result = neutral_guard("建议买入招商银行，目标价55.5")
        assert "建议买入" in result
        assert "目标价" not in result
