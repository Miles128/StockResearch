"""Output reading-mode and locale for LLM analysis (context-scoped).

Reading modes (replaces the old three-tier tone system):
- professional: 术语直接使用，数据完整，纯自然阅读（投研模式，无弹窗）
- friendly: 人话优先，必要术语可直接使用并自动带可点击弹窗（投顾模式）

`enable_glossary` 独立控制词库弹窗标记，默认开启（投顾模式），
投研模式由前端显式传 false。与 reading_mode 解耦，避免历史逻辑
"professional 才标记" 的反转问题。

The old "standard" tone has been removed — it was a vague middle ground
that conflicted with the explicit two-mode design in PRODUCT_STRATEGY.md.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar, Token
from typing import Literal

ReadingMode = Literal["professional", "friendly"]
OutputLocale = Literal["zh", "en"]

DEFAULT_READING_MODE: ReadingMode = "friendly"
DEFAULT_LOCALE: OutputLocale = "zh"
# 默认开启词库弹窗（投顾模式默认值；投研模式由前端显式传 false）。
DEFAULT_ENABLE_GLOSSARY: bool = True

_reading_mode_var: ContextVar[ReadingMode] = ContextVar(
    "reading_mode", default=DEFAULT_READING_MODE
)
_locale_var: ContextVar[OutputLocale] = ContextVar("output_locale", default=DEFAULT_LOCALE)
_enable_glossary_var: ContextVar[bool] = ContextVar(
    "enable_glossary", default=DEFAULT_ENABLE_GLOSSARY
)

_READING_MODE_INSTRUCTIONS: dict[ReadingMode, str] = {
    "professional": (
        "【专业写作规则】\n"
        "1. 术语直接使用，数据完整呈现\n"
        "2. 关键指标首次出现时附行业标准对比\n"
        "3. 保持投研报告的专业口径，客观克制\n"
        "示例：✅ \"ROE 32.1%（行业均值 18.2%），毛利率 52.3%\""
    ),
    "friendly": (
        "【友善写作规则】\n"
        "1. 用日常语言，但必要的金融术语可直接使用——它们会自动变成可点击的通俗解释，无需在文中用括号额外解释\n"
        "2. 数字必须带\"意味着什么\"的解释，不能只列数字\n"
        "3. 把指标翻译成钱的感受：不说\"VaR 4.32%\"，说\"95% 概率一天亏不超过 ¥2,300\"\n"
        "4. 类比优先：PE = \"花多少钱买1元年利润\"，ROE = \"每100元本金能赚多少\"\n"
        "5. 任何涉及板块轮动、风格切换、资金切换、龙头切换的结论，必须在同一句话内明确标注信号倾向（偏多/偏空/中性），并说明对谁有利、对谁不利；禁止把信号暗示留到后文\n"
        "6. 不要凭空给出\"轮动效应\"等判断；若证据不足，直接说\"暂时看不出明确轮动\"\n"
        "示例：\n"
        "  ❌ \"ROE 32.1%，毛利率 52.3%\"\n"
        "  ✅ \"赚钱能力很强——每100元本金一年能赚32元，行业平均才18元。"
        "每100元收入能留下52元利润。\"\n"
        "  ✅ \"存储板块市值增长快，与白酒形成轮动迹象——这通常意味着资金从白酒等防御板块流出、转向科技成长板块，信号偏乐观（看多）存储，偏谨慎（看空）白酒。\""
    ),
}

_LOCALE_INSTRUCTIONS: dict[OutputLocale, str] = {
    "zh": "输出语言：简体中文。",
    "en": "Output language: English only. Write all analysis in natural financial English.",
}


def normalize_reading_mode(value: str | None) -> ReadingMode:
    """Normalize reading mode, accepting both new and legacy values.

    Legacy mappings:
    - "professional" → "professional" (unchanged)
    - "standard" → "professional" (closest match)
    - "friendly" → "friendly" (unchanged)
    """
    if value in _READING_MODE_INSTRUCTIONS:
        return value
    if value == "standard":
        return "professional"
    return DEFAULT_READING_MODE


def normalize_locale(value: str | None) -> OutputLocale:
    if value == "zh":
        return "zh"
    if value == "en":
        return "en"
    return DEFAULT_LOCALE


def normalize_enable_glossary(value: bool | None) -> bool:
    """词库弹窗开关归一化。None 时按投顾默认开启。"""
    if value is None:
        return DEFAULT_ENABLE_GLOSSARY
    return bool(value)


# ── Backward-compatible aliases ──
OutputTone = ReadingMode
DEFAULT_TONE = DEFAULT_READING_MODE


def normalize_tone(value: str | None) -> ReadingMode:
    """Backward-compatible alias for normalize_reading_mode."""
    return normalize_reading_mode(value)


def set_output_style(
    *,
    tone: str | None = None,
    reading_mode: str | None = None,
    locale: str | None = None,
    enable_glossary: bool | None = None,
) -> tuple[Token[ReadingMode], Token[OutputLocale], Token[bool]]:
    """Set the output style context variables.

    Accepts both `tone` (legacy) and `reading_mode` (new) parameters.
    If both are provided, `reading_mode` takes precedence.
    `enable_glossary` 控制是否对输出做词库弹窗标记（仅投顾模式开启）。
    """
    mode = reading_mode or tone
    mode_token = _reading_mode_var.set(normalize_reading_mode(mode))
    locale_token = _locale_var.set(normalize_locale(locale))
    glossary_token = _enable_glossary_var.set(normalize_enable_glossary(enable_glossary))
    return mode_token, locale_token, glossary_token


def reset_output_style(
    tokens: tuple[Token[ReadingMode], Token[OutputLocale], Token[bool]],
) -> None:
    mode_token, locale_token, glossary_token = tokens
    _reading_mode_var.reset(mode_token)
    _locale_var.reset(locale_token)
    _enable_glossary_var.reset(glossary_token)


def get_output_locale() -> OutputLocale:
    return _locale_var.get()


def get_reading_mode() -> ReadingMode:
    return _reading_mode_var.get()


def get_enable_glossary() -> bool:
    return _enable_glossary_var.get()


def style_instruction_suffix() -> str:
    mode = _reading_mode_var.get()
    locale = _locale_var.get()
    parts = [_READING_MODE_INSTRUCTIONS[mode], _LOCALE_INSTRUCTIONS[locale]]
    return "\n".join(parts)


def apply_style_to_system(system: str) -> str:
    suffix = style_instruction_suffix()
    if not suffix:
        return system
    return f"{system.rstrip()}\n\n【输出要求】\n{suffix}"


@contextmanager
def output_style_scope(
    *,
    tone: str | None = None,
    reading_mode: str | None = None,
    locale: str | None = None,
    enable_glossary: bool | None = None,
) -> Iterator[None]:
    tokens = set_output_style(
        tone=tone,
        reading_mode=reading_mode,
        locale=locale,
        enable_glossary=enable_glossary,
    )
    try:
        yield
    finally:
        reset_output_style(tokens)


@asynccontextmanager
async def async_output_style_scope(
    *,
    tone: str | None = None,
    reading_mode: str | None = None,
    locale: str | None = None,
    enable_glossary: bool | None = None,
) -> AsyncIterator[None]:
    tokens = set_output_style(
        tone=tone,
        reading_mode=reading_mode,
        locale=locale,
        enable_glossary=enable_glossary,
    )
    try:
        yield
    finally:
        reset_output_style(tokens)
