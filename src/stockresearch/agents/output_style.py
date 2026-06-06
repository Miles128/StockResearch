"""Output tone and locale for LLM analysis (context-scoped)."""

from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from typing import AsyncIterator, Iterator, Literal

OutputTone = Literal["professional", "standard", "friendly"]
OutputLocale = Literal["zh", "en"]

DEFAULT_TONE: OutputTone = "professional"
DEFAULT_LOCALE: OutputLocale = "zh"

_tone_var: ContextVar[OutputTone] = ContextVar("output_tone", default=DEFAULT_TONE)
_locale_var: ContextVar[OutputLocale] = ContextVar("output_locale", default=DEFAULT_LOCALE)

_TONE_INSTRUCTIONS: dict[OutputTone, str] = {
    "professional": (
        "文风：非常专业投研口径，引用具体数据与指标，表述客观、克制，可使用行业术语。"
    ),
    "standard": (
        "文风：普通投研口吻，清晰平衡，兼顾专业性与可读性，避免过度术语堆砌。"
    ),
    "friendly": (
        "文风：平易近人，用通俗语言解释要点，少用行话，必要时简短举例，让非专业读者也能理解。"
    ),
}

_LOCALE_INSTRUCTIONS: dict[OutputLocale, str] = {
    "zh": "输出语言：简体中文。",
    "en": "Output language: English only. Write all analysis in natural financial English.",
}


def normalize_tone(value: str | None) -> OutputTone:
    if value in _TONE_INSTRUCTIONS:
        return value  # type: ignore[return-value]
    return DEFAULT_TONE


def normalize_locale(value: str | None) -> OutputLocale:
    if value in ("zh", "en"):
        return value  # type: ignore[return-value]
    return DEFAULT_LOCALE


def set_output_style(
    *,
    tone: str | None = None,
    locale: str | None = None,
) -> tuple[ContextVar.Token[OutputTone], ContextVar.Token[OutputLocale]]:
    tone_token = _tone_var.set(normalize_tone(tone))
    locale_token = _locale_var.set(normalize_locale(locale))
    return tone_token, locale_token


def reset_output_style(
    tokens: tuple[ContextVar.Token[OutputTone], ContextVar.Token[OutputLocale]],
) -> None:
    tone_token, locale_token = tokens
    _tone_var.reset(tone_token)
    _locale_var.reset(locale_token)


def get_output_locale() -> OutputLocale:
    return _locale_var.get()


def style_instruction_suffix() -> str:
    tone = _tone_var.get()
    locale = _locale_var.get()
    parts = [_TONE_INSTRUCTIONS[tone], _LOCALE_INSTRUCTIONS[locale]]
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
    locale: str | None = None,
) -> Iterator[None]:
    tokens = set_output_style(tone=tone, locale=locale)
    try:
        yield
    finally:
        reset_output_style(tokens)


@asynccontextmanager
async def async_output_style_scope(
    *,
    tone: str | None = None,
    locale: str | None = None,
) -> AsyncIterator[None]:
    tokens = set_output_style(tone=tone, locale=locale)
    try:
        yield
    finally:
        reset_output_style(tokens)
