"""Summary length normalization tests."""

from stockresearch.agents.research.summary_length import normalize_summary


def test_normalize_summary_keeps_mid_band() -> None:
    text = "综合偏多，估值合理，基本面与情绪面共振，筹码结构相对稳定。" * 5
    assert 120 <= len(text) <= 180
    assert normalize_summary(text) == text


def test_normalize_summary_compresses_long_text() -> None:
    long = "结论。" * 80
    result = normalize_summary(long)
    assert len(result) <= 180


def test_normalize_summary_expands_short_text() -> None:
    short = "贵州茅台(600519) 加权综合 7.2/10，倾向偏多。"
    hints = [
        "基本面盈利质量持续改善，营收与利润增速位于行业中上水平，估值分位处于近五年中枢附近。",
        "情绪面新闻与政策口径偏暖，北向与两融资金小幅净流入，市场风险偏好有所回升。",
        "技术面短期均线呈多头排列，但成交量仍未有效放大，需观察后续放量确认。",
    ]
    result = normalize_summary(short, expand_parts=hints)
    assert 120 <= len(result) <= 180
    assert result.startswith("贵州茅台")
