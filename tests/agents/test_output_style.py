"""Tests for analysis output tone and locale injection."""

from stockresearch.agents.output_style import (
    apply_style_to_system,
    output_style_scope,
    style_instruction_suffix,
)


def test_default_style_is_professional_zh():
    assert "非常专业" in style_instruction_suffix()
    assert "简体中文" in style_instruction_suffix()


def test_friendly_tone_instruction():
    with output_style_scope(tone="friendly", locale="zh"):
        suffix = style_instruction_suffix()
    assert "平易近人" in suffix


def test_english_locale_instruction():
    with output_style_scope(tone="professional", locale="en"):
        suffix = style_instruction_suffix()
    assert "English" in suffix


def test_apply_style_appends_to_system():
    with output_style_scope(tone="standard", locale="en"):
        styled = apply_style_to_system("You are an analyst.")
    assert styled.startswith("You are an analyst.")
    assert "【输出要求】" in styled
    assert "English" in styled
