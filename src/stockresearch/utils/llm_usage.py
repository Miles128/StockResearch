"""Per-request LLM token usage accumulation and cost estimates."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from stockresearch.core.schemas import LlmUsageOut

# USD per 1M tokens (input, output) — rough public list prices for estimates only.
_MODEL_PRICING_USD: dict[str, tuple[float, float]] = {
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
    "qwen-plus": (0.40, 1.20),
    "qwen-turbo": (0.05, 0.20),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}
_DEFAULT_PRICING_USD = (1.0, 2.0)
_CNY_PER_USD = 7.2


@dataclass
class LlmUsageTotals:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    is_estimate: bool = False
    call_count: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


_usage_ctx: ContextVar[LlmUsageTotals | None] = ContextVar("llm_usage_totals", default=None)


def reset_usage(*, model: str = "") -> LlmUsageTotals:
    totals = LlmUsageTotals(model=model.strip())
    _usage_ctx.set(totals)
    return totals


def get_usage() -> LlmUsageTotals | None:
    return _usage_ctx.get()


def clear_usage() -> None:
    _usage_ctx.set(None)


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    # Mixed CN/EN heuristic: ~2 chars per token for CJK-heavy text.
    return max(1, len(text) // 2)


def record_usage(
    *,
    prompt_tokens: int,
    completion_tokens: int,
    is_estimate: bool = False,
) -> None:
    totals = _usage_ctx.get()
    if totals is None:
        return
    totals.prompt_tokens += max(0, prompt_tokens)
    totals.completion_tokens += max(0, completion_tokens)
    totals.is_estimate = totals.is_estimate or is_estimate
    totals.call_count += 1


def _estimate_cost_cny(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    if prompt_tokens <= 0 and completion_tokens <= 0:
        return None
    key = model.lower().strip()
    inp, out = _DEFAULT_PRICING_USD
    for name, pricing in _MODEL_PRICING_USD.items():
        if name in key:
            inp, out = pricing
            break
    usd = (prompt_tokens * inp + completion_tokens * out) / 1_000_000
    return round(usd * _CNY_PER_USD, 4)


def usage_to_out(totals: LlmUsageTotals | None) -> LlmUsageOut | None:
    if totals is None or totals.total_tokens <= 0:
        return None
    return LlmUsageOut(
        prompt_tokens=totals.prompt_tokens,
        completion_tokens=totals.completion_tokens,
        total_tokens=totals.total_tokens,
        model=totals.model or None,
        estimated_cost_cny=_estimate_cost_cny(
            totals.model,
            totals.prompt_tokens,
            totals.completion_tokens,
        ),
        is_estimate=totals.is_estimate,
        llm_calls=totals.call_count,
    )
