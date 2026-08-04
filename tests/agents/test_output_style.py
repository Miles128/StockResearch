"""Tests for analysis output reading-mode and locale injection."""

from stockresearch.core.output_style import (
    apply_style_to_system,
    normalize_reading_mode,
    output_style_scope,
    style_instruction_suffix,
)


def test_default_style_is_friendly_zh():
    suffix = style_instruction_suffix()
    assert "普通版表达规则" in suffix
    assert "简体中文" in suffix


def test_professional_mode_instruction():
    with output_style_scope(reading_mode="professional", locale="zh"):
        suffix = style_instruction_suffix()
    assert "专业写作规则" in suffix


def test_standard_mode_normalizes_to_friendly():
    with output_style_scope(reading_mode="standard", locale="zh"):
        suffix = style_instruction_suffix()
    assert "普通版表达规则" in suffix
    assert "专业写作规则" not in suffix


def test_friendly_mode_instruction():
    with output_style_scope(reading_mode="friendly", locale="zh"):
        suffix = style_instruction_suffix()
    assert "普通版表达规则" in suffix


def test_english_locale_instruction():
    with output_style_scope(reading_mode="professional", locale="en"):
        suffix = style_instruction_suffix()
    assert "English" in suffix


def test_apply_style_appends_to_system():
    with output_style_scope(reading_mode="professional", locale="en"):
        styled = apply_style_to_system("You are an analyst.")
    assert styled.startswith("You are an analyst.")
    assert "【输出要求】" in styled
    assert "English" in styled


def test_standard_maps_to_friendly():
    assert normalize_reading_mode("standard") == "friendly"


def test_legacy_tone_professional_unchanged():
    assert normalize_reading_mode("professional") == "professional"


def test_legacy_tone_friendly_unchanged():
    assert normalize_reading_mode("friendly") == "friendly"


def test_invalid_tone_defaults_to_friendly():
    assert normalize_reading_mode("unknown") == "friendly"


def test_reading_mode_takes_precedence_over_tone():
    with output_style_scope(tone="friendly", reading_mode="professional", locale="zh"):
        suffix = style_instruction_suffix()
    assert "专业写作规则" in suffix
