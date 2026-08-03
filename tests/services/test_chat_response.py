from stockresearch.agents.output_style import output_style_scope
from stockresearch.core.schemas import DimensionResult, ResearchReportOut
from stockresearch.services.chat.response import (
    finalize_cards,
    finalize_chat_reply,
    finalize_research_report,
)


def test_finalize_chat_reply_applies_neutrality_and_partial_marker() -> None:
    with output_style_scope(reading_mode="friendly", locale="zh"):
        reply = finalize_chat_reply(
            "组合倾向减仓。以上内容由 AI 生成，仅供参考，不构成投资建议。",
            partial=True,
        )

    assert "减仓" not in reply
    assert "偏高" in reply
    assert "不构成投资建议" not in reply
    assert reply.endswith("（部分分析未完成）")


def test_finalize_chat_reply_allows_suggested_buy() -> None:
    with output_style_scope(reading_mode="friendly", locale="zh"):
        reply = finalize_chat_reply("建议买入招商银行。")

    assert "建议买入" in reply


def test_finalize_marks_chinese_short_labels() -> None:
    """友善模式常用中文简称也应被标记。"""
    with output_style_scope(reading_mode="friendly", locale="zh", enable_glossary=True):
        reply = finalize_chat_reply("当前市盈率 35.2，市净率 4.1")
    assert '<term data-id="PE">市盈率</term>' in reply
    assert '<term data-id="PB">市净率</term>' in reply


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


def test_finalize_research_report_marks_summary() -> None:
    with output_style_scope(reading_mode="friendly", locale="zh", enable_glossary=True):
        report = finalize_research_report(
            ResearchReportOut(
                symbol="600519",
                name="贵州茅台",
                dimensions={
                    "fundamental": DimensionResult(
                        agent="fundamental",
                        score=8.0,
                        confidence="high",
                        highlights=["ROE 32.1%"],
                        risks=["PE 偏高"],
                        data_sources=["akshare"],
                    )
                },
                composite_score=8.0,
                composite_confidence="high",
                bias="bullish",
                summary="当前 PE 35.2，ROE 32.1%。",
            )
        )
    assert '<term data-id="PE">PE</term>' in report.summary
    assert '<term data-id="ROE">ROE</term>' in report.dimensions["fundamental"].highlights[0]


def test_finalize_cards_marks_research_card() -> None:
    with output_style_scope(reading_mode="friendly", locale="zh", enable_glossary=True):
        cards = finalize_cards(
            [
                {
                    "type": "research",
                    "data": ResearchReportOut(
                        symbol="600519",
                        name="贵州茅台",
                        dimensions={},
                        composite_score=8.0,
                        composite_confidence="high",
                        bias="bullish",
                        summary="ROE 32.1%",
                    ).model_dump(mode="json"),
                }
            ]
        )
    summary = cards[0]["data"]["summary"]
    assert '<term data-id="ROE">ROE</term>' in summary


def test_finalize_cards_scrubs_target_price_in_evidence_snippet() -> None:
    """PRD §六: 目标价禁止 — research card evidence snippet 必须经 neutral_guard。

    Regression: 旧版 finalize_cards 只做术语标记，不调合规护栏，
    导致研报 target_price 字段以 "目标价1800" 形式直出 UI 证据条。
    """
    from stockresearch.core.schemas import DimensionEvidence

    with output_style_scope(reading_mode="professional", locale="zh", enable_glossary=False):
        report = ResearchReportOut(
            symbol="600519",
            name="贵州茅台",
            dimensions={
                "fundamental": DimensionResult(
                    agent="fundamental",
                    score=8.0,
                    confidence="high",
                    highlights=["业绩稳健"],
                    risks=["估值偏高"],
                    data_sources=["akshare"],
                    evidence=[
                        DimensionEvidence(
                            source="东财研报",
                            snippet="中金公司 买入 目标价1800 · 高端白酒竞争加剧",
                            kind="research_report",
                        )
                    ],
                )
            },
            composite_score=8.0,
            composite_confidence="high",
            bias="bullish",
            summary="建议加仓茅台",
        )
        finalized = finalize_cards([{"type": "research", "data": report.model_dump(mode="json")}])

    data = finalized[0]["data"]
    snippet = data["dimensions"]["fundamental"]["evidence"][0]["snippet"]
    summary = data["summary"]
    # 目标价必须被合规替换为"合理估值区间"
    assert "目标价1800" not in snippet
    assert "合理估值区间" in snippet
    # "建议加仓" 必须被替换为中性表达
    assert "加仓" not in summary


def test_finalize_research_report_runs_compliance_even_when_glossary_off() -> None:
    """合规护栏不依赖 glossary 开关（PRD §六 是硬约束，不是术语标记）。"""
    with output_style_scope(reading_mode="professional", locale="zh", enable_glossary=False):
        report = finalize_research_report(
            ResearchReportOut(
                symbol="600519",
                name="贵州茅台",
                dimensions={},
                composite_score=8.0,
                composite_confidence="high",
                bias="bullish",
                summary="建议减仓茅台",
            )
        )
    assert "减仓" not in report.summary
    # glossary 关闭时不应出现术语标记
    assert "<term" not in report.summary
