"""A-share factor checklist tests."""

from stockresearch.core.schemas import DimensionResult
from stockresearch.services.ashare_factors import build_ashare_factor_checklist


def test_ashare_factor_checklist_uses_existing_sources_only() -> None:
    factors = build_ashare_factor_checklist(
        {
            "technical": DimensionResult(
                agent="technical",
                score=6,
                confidence="medium",
                highlights=[],
                risks=[],
                data_sources=["akshare_kline", "sina_quote", "sina_trading_rules"],
            ),
            "chips": DimensionResult(
                agent="chips",
                score=5,
                confidence="medium",
                highlights=[],
                risks=[],
                data_sources=["akshare_lhb", "akshare_lockup"],
            ),
        },
        news_text_factor="新闻文本因子已生成",
    )

    by_name = {item.name: item for item in factors}
    assert by_name["K 线、均线与技术指标"].status == "verified"
    assert by_name["涨跌停 / ST / 停复牌"].status == "verified"
    assert by_name["龙虎榜与游资席位"].status == "verified"
    assert by_name["限售解禁"].status == "verified"
    assert by_name["主力资金流向"].status == "missing"
    assert by_name["雪球/东财情绪"].status == "missing"
    assert by_name["新闻、政策与事件文本"].status == "verified"
    assert not by_name["涨跌停 / ST / 停复牌"].missing
    trading_sources = {
        source.key: source for source in by_name["涨跌停 / ST / 停复牌"].source_details
    }
    assert trading_sources["sina_trading_rules"].provider == "sina"
    assert trading_sources["sina_trading_rules"].layer == "L1"
    assert trading_sources["sina_trading_rules"].status == "verified"
    fund_sources = {source.key: source for source in by_name["主力资金流向"].source_details}
    assert fund_sources["akshare_fund_flow"].status == "missing"
