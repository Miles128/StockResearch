from stockresearch.agents.output_style import output_style_scope
from stockresearch.services.chat_response import finalize_chat_reply


def test_finalize_chat_reply_applies_neutrality_and_partial_marker() -> None:
    with output_style_scope(reading_mode="friendly", locale="zh"):
        reply = finalize_chat_reply(
            "建议买入。以上内容由 AI 生成，仅供参考，不构成投资建议。",
            partial=True,
        )

    assert "建议买入" not in reply
    assert "不构成投资建议" not in reply
    assert reply.endswith("（部分分析未完成）")


def test_finalize_marks_terms_when_glossary_enabled() -> None:
    """投顾模式（enable_glossary=True）应标记术语为可点击。"""
    with output_style_scope(reading_mode="friendly", locale="zh", enable_glossary=True):
        reply = finalize_chat_reply("招商银行 ROE 32.1%，毛利率 52.3%")
    assert '<term data-id="ROE">ROE</term>' in reply
    assert '<term data-id="毛利率">毛利率</term>' in reply


def test_finalize_skips_terms_when_glossary_disabled() -> None:
    """投研模式（enable_glossary=False）不应标记术语。"""
    with output_style_scope(reading_mode="professional", locale="zh", enable_glossary=False):
        reply = finalize_chat_reply("招商银行 ROE 32.1%，毛利率 52.3%")
    assert "<term" not in reply
    assert "ROE" in reply


def test_finalize_marks_terms_by_default() -> None:
    """未显式传 enable_glossary 时按投顾默认开启标记。"""
    with output_style_scope(reading_mode="friendly", locale="zh"):
        reply = finalize_chat_reply("ROE 32.1%")
    assert '<term data-id="ROE">ROE</term>' in reply


def test_finalize_no_marking_when_reading_mode_professional_without_glossary() -> None:
    """reading_mode=professional 单独不足以触发标记（旧反转逻辑已修复）。"""
    with output_style_scope(reading_mode="professional", locale="zh", enable_glossary=False):
        reply = finalize_chat_reply("ROE 32.1%")
    assert "<term" not in reply
