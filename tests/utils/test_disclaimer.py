"""Disclaimer stripping tests."""

from stockresearch.utils.disclaimer import strip_disclaimer


def test_strip_disclaimer_removes_trailing_notice() -> None:
    raw = "结论偏多。\n\n以上内容由 AI 生成，仅供参考，不构成投资建议。"
    assert strip_disclaimer(raw) == "结论偏多。"


def test_strip_disclaimer_removes_new_wording() -> None:
    raw = "结论偏多。\n\n以下内容由 AI 生成，仅供参考，不构成投资建议。"
    assert strip_disclaimer(raw) == "结论偏多。"


def test_strip_disclaimer_preserves_body_without_notice() -> None:
    assert strip_disclaimer("仅四维分析结论。") == "仅四维分析结论。"
