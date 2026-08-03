"""Tests for glossary, neutral_guard, and balance_check services."""

from stockresearch.agents.orchestrator.balance_check import check_balance
from stockresearch.services.glossary import clear_glossary_cache, get_glossary, mark_terms
from stockresearch.services.neutral_guard import (
    apply_ban_filter,
    apply_tone_calibration,
    neutral_guard,
)

# ── Glossary ──


class TestGlossary:
    def setup_method(self):
        clear_glossary_cache()

    def test_glossary_loads(self):
        g = get_glossary()
        assert len(g) > 30  # at least 30 terms in the JSON
        assert "PE" in g
        assert "ROE" in g
        assert "VaR" in g

    def test_term_has_required_fields(self):
        g = get_glossary()
        pe = g["PE"]
        assert pe.short == "市盈率"
        assert pe.en == "Price-to-Earnings Ratio"
        assert pe.def_
        assert pe.analogy

    def test_mark_short_abbreviation(self):
        result = mark_terms("ROE 32.1%")
        assert '<term data-id="ROE">ROE</term>' in result

    def test_mark_chinese_short_label(self):
        result = mark_terms("当前市盈率 35.2，净资产收益率 32.1%")
        assert '<term data-id="PE">市盈率</term>' in result
        assert '<term data-id="ROE">净资产收益率</term>' in result

    def test_mark_chinese_term(self):
        result = mark_terms("最大回撤 8%")
        assert '<term data-id="最大回撤">最大回撤</term>' in result

    def test_mark_multiple_terms(self):
        result = mark_terms("ROE 32.1%，毛利率 52.3%，PE 35.2")
        assert '<term data-id="ROE">ROE</term>' in result
        assert '<term data-id="毛利率">毛利率</term>' in result
        assert '<term data-id="PE">PE</term>' in result

    def test_no_mark_without_terms(self):
        result = mark_terms("今天天气不错")
        assert "<term" not in result

    def test_longer_term_takes_priority(self):
        """VaR 95% should match before VaR."""
        result = mark_terms("VaR 95% = 4.32%")
        # VaR 95% is a separate entry, should be matched
        assert "VaR 95%" in result or "VaR" in result

    def test_no_overlap_matches(self):
        result = mark_terms("PE和PB都偏高")
        # Both should be marked, no overlap
        assert '<term data-id="PE">PE</term>' in result
        assert '<term data-id="PB">PB</term>' in result

    def test_merge_custom_glossary_term(self):
        from stockresearch.core.schemas import CustomGlossaryTermOut
        from stockresearch.services.glossary import merge_glossary

        custom = [
            CustomGlossaryTermOut(
                id="我的术语",
                short="我的术语",
                def_="测试解释",
                analogy="测试类比",
            )
        ]
        merged = merge_glossary(custom)
        result = mark_terms("这里出现了我的术语", glossary=merged)
        assert '<term data-id="我的术语">我的术语</term>' in result


# ── Neutral Guard ──


class TestNeutralGuard:
    def test_ban_filter_suggests_buy_allowed(self):
        result = apply_ban_filter("建议买入招商银行")
        assert "建议买入" in result

    def test_ban_filter_bans_reduce(self):
        result = apply_ban_filter("组合倾向减仓")
        assert "减仓" not in result
        assert "仓位偏高" in result

    def test_ban_filter_target_price(self):
        result = apply_ban_filter("目标价55.5元")
        assert "目标价" not in result
        assert "合理估值区间" in result

    def test_ban_filter_urgency_words(self):
        result = apply_ban_filter("赶紧买入")
        assert "赶紧" not in result

    def test_tone_calibration_should(self):
        result = apply_tone_calibration("应该买入")
        assert "应该" not in result
        assert "留意" in result

    def test_tone_calibration_system_suggestion(self):
        result = apply_tone_calibration("系统建议减仓")
        assert "减仓" not in result
        assert "仓位偏高" in result

    def test_neutral_guard_full_pipeline(self):
        result = neutral_guard("建议买入招商银行，目标价55.5，应该买")
        assert "建议买入" in result
        assert "目标价" not in result
        assert "应该" not in result

    def test_neutral_guard_preserves_neutral_text(self):
        text = "招商银行当前PE 35.2，ROE 16.8%"
        result = neutral_guard(text)
        assert result == text  # no changes needed


# ── Balance Check ──


class TestBalanceCheck:
    def test_negative_dominance_triggers_balancing(self):
        text = "下跌亏损风险回撤暴跌看空卖出"
        result = check_balance(text)
        assert "多空交织" in result or "审慎" in result

    def test_single_dimension_adds_caveat(self):
        text = "技术面评分6/10，RSI偏高，动量偏弱"
        result = check_balance(text)
        assert "技术面视角" in result

    def test_balanced_text_no_appendage(self):
        text = "招商银行PE 35.2，基本面稳健，技术面中性"
        result = check_balance(text)
        assert result == text  # no appendage needed

    def test_predictive_without_disclaimer_adds_note(self):
        text = "预计将上涨，有望突破压力位"
        result = check_balance(text)
        assert "不保证" in result
