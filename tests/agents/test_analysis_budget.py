"""Analysis depth budget resolution and tier differences."""

from stockresearch.agents.research.budget import (
    budget_for_depth,
    is_gap_close_utterance,
    parse_depth_from_text,
    resolve_analysis_depth,
)


def test_parse_depth_from_text_prefers_deep() -> None:
    assert parse_depth_from_text("请深度分析茅台") == "deep"
    assert parse_depth_from_text("综合分析一下宁德时代") == "comprehensive"
    assert parse_depth_from_text("茅台现在怎么样") is None


def test_is_gap_close_utterance() -> None:
    assert is_gap_close_utterance("只补缺口再跑 综合分析茅台（600519）") is True
    assert is_gap_close_utterance("补充数据：龙虎榜") is True
    assert is_gap_close_utterance("补充数据并重新投研 600519：财务") is True
    assert is_gap_close_utterance("分析一下茅台") is False


def test_resolve_priority_explicit_over_utterance_over_settings() -> None:
    assert (
        resolve_analysis_depth(
            explicit="standard",
            utterance="深度分析茅台",
            settings_depth="comprehensive",
        )
        == "standard"
    )
    assert (
        resolve_analysis_depth(
            explicit=None,
            utterance="深度分析茅台",
            settings_depth="comprehensive",
        )
        == "deep"
    )
    assert (
        resolve_analysis_depth(
            explicit=None,
            utterance="看看行情",
            settings_depth="comprehensive",
        )
        == "comprehensive"
    )
    assert (
        resolve_analysis_depth(
            explicit=None,
            utterance=None,
            settings_depth=None,
        )
        == "standard"
    )


def test_budget_tiers_differ() -> None:
    standard = budget_for_depth("standard")
    comprehensive = budget_for_depth("comprehensive")
    deep = budget_for_depth("deep")

    assert standard.ann_limit == 8
    assert comprehensive.prefer_earnings_anns is True
    assert comprehensive.news_cluster is True
    assert comprehensive.factors_expanded is True
    assert "roe_ttm" in comprehensive.factor_keys

    assert deep.ann_limit > comprehensive.ann_limit
    assert deep.news_deep_cross_check == 2
    assert deep.enable_signal_verify_hook is True
    assert deep.financial_periods >= comprehensive.financial_periods
    assert len(deep.factor_keys) >= len(standard.factor_keys)
