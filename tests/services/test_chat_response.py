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
