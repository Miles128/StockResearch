"""Output reading-mode and locale for LLM analysis (context-scoped).

Reading modes (两档表达风格):
- friendly: 普通版（默认），平实克制，术语首现必解释，数字翻译成影响
- professional: 专业版，术语直出、数据完整

普通版完整规范见 `prompts/advisor_plain_language.md`，此处为内联短版。
存量三档中的 `standard` 一律归一为 `friendly`（`normalize_reading_mode`）。

`enable_glossary` 独立控制词库弹窗标记，与 reading_mode 解耦。
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Literal

from stockresearch.core.schemas import CustomGlossaryTermOut

ReadingMode = Literal["friendly", "professional"]
OutputLocale = Literal["zh", "en"]

DEFAULT_READING_MODE: ReadingMode = "friendly"
DEFAULT_LOCALE: OutputLocale = "zh"
DEFAULT_ENABLE_GLOSSARY: bool = True

_reading_mode_var: ContextVar[ReadingMode] = ContextVar(
    "reading_mode", default=DEFAULT_READING_MODE
)
_locale_var: ContextVar[OutputLocale] = ContextVar("output_locale", default=DEFAULT_LOCALE)
_enable_glossary_var: ContextVar[bool] = ContextVar(
    "enable_glossary", default=DEFAULT_ENABLE_GLOSSARY
)
_custom_glossary_var: ContextVar[tuple[CustomGlossaryTermOut, ...]] = ContextVar(
    "custom_glossary", default=()
)

_READING_MODE_INSTRUCTIONS: dict[ReadingMode, str] = {
    "friendly": (
        "【普通版表达规则 · 必读】\n"
        "1. 用平实、自然、克制的语言；结论清楚（一句话），原因简短（不超过 3 条），风险明确（不埋在文末）\n"
        "2. 专业名词第一次出现必须用半句白话解释（如「估值分位——现在比过去大多数时候都贵/便宜」）；\n"
        "   禁止不加解释地连用：估值分位、动量、风险敞口、夏普比率、回撤、边际变化等词\n"
        "3. 数字必须翻译成对用户的影响：不说「回撤 12%」，说「从最高点算，每 100 块最多亏了 12 块」\n"
        "4. 类比优先且不轻浮：PE = 「花多少钱买 1 元年利润」，ROE = 「每 100 元本金一年能赚多少」\n"
        "5. 风险提示、不确定性、免责信息必须保留，放在结论附近而非末尾\n"
        "6. 建议以选项形式给出（「可以…也可以…也可以先不动」），不下交易指令\n"
        "7. 证据不足时明确说「暂时看不出」，不编造、不外推\n"
        "8. 板块轮动类结论须在同一句话内标注偏多/偏空/中性\n"
        "示例：\n"
        '  ❌ "ROE 32.1%，毛利率 52.3%，估值分位 78%，动量走强"\n'
        '  ✅ "赚钱能力很强——每 100 元本金一年能赚 32 元，行业平均才 18 元；"\n'
        '      "但现在价格比过去 78% 的时间都贵，留意回调风险。"'
    ),
    "professional": (
        "【专业写作规则】\n"
        "1. 术语直接使用，数据完整呈现\n"
        "2. 关键指标首次出现时附行业标准对比\n"
        "3. 保持投研报告的专业口径，客观克制\n"
        '示例：✅ "ROE 32.1%（行业均值 18.2%），毛利率 52.3%"'
    ),
}

_LOCALE_INSTRUCTIONS: dict[OutputLocale, str] = {
    "zh": "输出语言：简体中文。",
    "en": "Output language: English only. Write all analysis in natural financial English.",
}


def normalize_reading_mode(value: str | None) -> ReadingMode:
    if value == "professional":
        return "professional"
    # friendly 为默认；存量三档中的 standard 一并归一为普通版
    return "friendly"


def normalize_locale(value: str | None) -> OutputLocale:
    if value == "zh":
        return "zh"
    if value == "en":
        return "en"
    return DEFAULT_LOCALE


def normalize_enable_glossary(value: bool | None) -> bool:
    if value is None:
        return DEFAULT_ENABLE_GLOSSARY
    return bool(value)


def set_output_style(
    *,
    tone: str | None = None,
    reading_mode: str | None = None,
    locale: str | None = None,
    enable_glossary: bool | None = None,
    custom_glossary: Sequence[CustomGlossaryTermOut] | None = None,
) -> tuple[
    Token[ReadingMode], Token[OutputLocale], Token[bool], Token[tuple[CustomGlossaryTermOut, ...]]
]:
    mode = reading_mode or tone
    mode_token = _reading_mode_var.set(normalize_reading_mode(mode))
    locale_token = _locale_var.set(normalize_locale(locale))
    glossary_token = _enable_glossary_var.set(normalize_enable_glossary(enable_glossary))
    custom = tuple(custom_glossary or ())
    custom_token = _custom_glossary_var.set(custom)
    return mode_token, locale_token, glossary_token, custom_token


def reset_output_style(
    tokens: tuple[
        Token[ReadingMode],
        Token[OutputLocale],
        Token[bool],
        Token[tuple[CustomGlossaryTermOut, ...]],
    ],
) -> None:
    mode_token, locale_token, glossary_token, custom_token = tokens
    _reading_mode_var.reset(mode_token)
    _locale_var.reset(locale_token)
    _enable_glossary_var.reset(glossary_token)
    _custom_glossary_var.reset(custom_token)


def get_output_locale() -> OutputLocale:
    return _locale_var.get()


def get_reading_mode() -> ReadingMode:
    return _reading_mode_var.get()


def get_enable_glossary() -> bool:
    return _enable_glossary_var.get()


def get_custom_glossary() -> tuple[CustomGlossaryTermOut, ...]:
    return _custom_glossary_var.get()


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
    custom_glossary: Sequence[CustomGlossaryTermOut] | None = None,
) -> Iterator[None]:
    tokens = set_output_style(
        tone=tone,
        reading_mode=reading_mode,
        locale=locale,
        enable_glossary=enable_glossary,
        custom_glossary=custom_glossary,
    )
    try:
        yield
    finally:
        reset_output_style(tokens)
