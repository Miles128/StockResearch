"""Output reading-mode and locale for LLM analysis (context-scoped).

Reading modes (三档表达风格):
- friendly: 友善白话，日常语言为主，少术语
- standard: 标准口径，中文术语+简要解释，平衡可读与专业
- professional: 专业投研，术语直出、数据完整

`enable_glossary` 独立控制词库弹窗标记，与 reading_mode 解耦。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar, Token
from typing import Literal

from stockresearch.core.schemas import CustomGlossaryTermOut

ReadingMode = Literal["friendly", "standard", "professional"]
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
        "【友善白话规则】\n"
        "1. 以日常语言为主，尽量少用英文缩写；必须出现时可保留（系统自动加可点击解释）\n"
        "2. 数字必须带\"意味着什么\"的解释，不能只列数字\n"
        "3. 把指标翻译成钱的感受：不说\"VaR 4.32%\"，说\"95% 概率一天亏不超过 ¥2,300\"\n"
        "4. 类比优先：PE = \"花多少钱买1元年利润\"，ROE = \"每100元本金能赚多少\"\n"
        "5. 板块轮动类结论须在同一句话内标注偏多/偏空/中性；证据不足时说\"暂时看不出明确轮动\"\n"
        "示例：\n"
        "  ❌ \"ROE 32.1%，毛利率 52.3%\"\n"
        "  ✅ \"赚钱能力很强——每100元本金一年能赚32元，行业平均才18元。\""
    ),
    "standard": (
        "【标准表达规则】\n"
        "1. 使用常见中文金融术语（市盈率、净资产收益率等），首次出现时用半句白话点明含义\n"
        "2. 数据完整呈现，关键数字附一句\"意味着什么\"或行业对比\n"
        "3. 避免堆砌英文缩写；必要时保留 PE/ROE 等并配合中文说法\n"
        "4. 语气客观克制，结构清晰：先结论后依据\n"
        "示例：✅ \"市盈率 35 倍，略高于行业均值 28 倍，估值偏贵；净资产收益率 32%，赚钱能力仍属上游。\""
    ),
    "professional": (
        "【专业写作规则】\n"
        "1. 术语直接使用，数据完整呈现\n"
        "2. 关键指标首次出现时附行业标准对比\n"
        "3. 保持投研报告的专业口径，客观克制\n"
        "示例：✅ \"ROE 32.1%（行业均值 18.2%），毛利率 52.3%\""
    ),
}

_LOCALE_INSTRUCTIONS: dict[OutputLocale, str] = {
    "zh": "输出语言：简体中文。",
    "en": "Output language: English only. Write all analysis in natural financial English.",
}


def normalize_reading_mode(value: str | None) -> ReadingMode:
    if value in _READING_MODE_INSTRUCTIONS:
        return value  # type: ignore[return-value]
    if value == "standard":
        return "standard"
    return DEFAULT_READING_MODE


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


OutputTone = ReadingMode
DEFAULT_TONE = DEFAULT_READING_MODE


def normalize_tone(value: str | None) -> ReadingMode:
    return normalize_reading_mode(value)


def set_output_style(
    *,
    tone: str | None = None,
    reading_mode: str | None = None,
    locale: str | None = None,
    enable_glossary: bool | None = None,
    custom_glossary: Sequence[CustomGlossaryTermOut] | None = None,
) -> tuple[Token[ReadingMode], Token[OutputLocale], Token[bool], Token[tuple[CustomGlossaryTermOut, ...]]]:
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


@asynccontextmanager
async def async_output_style_scope(
    *,
    tone: str | None = None,
    reading_mode: str | None = None,
    locale: str | None = None,
    enable_glossary: bool | None = None,
    custom_glossary: Sequence[CustomGlossaryTermOut] | None = None,
) -> AsyncIterator[None]:
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
