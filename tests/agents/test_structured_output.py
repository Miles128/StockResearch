"""Structured LLM output parsing tests."""

from stockresearch.agents.structured_output import ResearchJudgeOut, VoteLabelOut


def test_research_judge_parses_json() -> None:
    raw = '{"bias":"偏多","summary":"估值合理","reason":"盈利稳定","divergence":"分歧小","divergence_point":"无"}'
    parsed = ResearchJudgeOut.from_llm(raw)
    assert parsed.final_bias == "bullish"
    assert parsed.summary == "估值合理"
    assert parsed.divergence == "分歧小"


def test_research_judge_fallback_text() -> None:
    parsed = ResearchJudgeOut.from_llm("整体偏空，动量走弱")
    assert parsed.final_bias == "bearish"
    assert parsed.summary


def test_vote_label_parses_token() -> None:
    assert VoteLabelOut.from_llm("综合看，偏多").vote == "偏多"
    assert VoteLabelOut.from_llm("无明确信号").vote == "中性"
