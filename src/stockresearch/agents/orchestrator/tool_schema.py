"""Tool-call schema validation — zero-dependency reliability layer.

Orchestrator ReAct loops parse free-form JSON tool calls out of LLM text.
Before execution each call is validated and normalized here (the cheap,
framework-free version of what Pydantic-AI provides through typed tool
schemas):

- the tool name must resolve to a known tool/skill (legacy aliases normalize)
- args must be a JSON object
- numeric scalars coerce to str (symbols are digits); bools stay bool

Failed calls return a corrective Chinese message so the loop can retry
with the error injected into context.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from stockresearch.agents.orchestrator.skills import SKILL_IDS

LEGACY_SKILL_ALIASES: dict[str, str] = {
    "get_stock_research": "skill_stock_research",
    "debate_stock": "skill_bull_bear_debate",
}


class _ToolCall(BaseModel):
    tool: str = Field(min_length=1)
    args: dict[str, Any] = Field(default_factory=dict)


def _coerce_scalars(args: dict[str, Any]) -> dict[str, Any]:
    """int/float -> str (symbols are digits), bool kept as-is (with_debate etc.)."""
    return {
        key: (
            value
            if isinstance(value, bool)
            else str(value)
            if isinstance(value, (int, float))
            else value
        )
        for key, value in args.items()
    }


class ToolCallValidator:
    """Validate and normalize a single LLM-produced tool call."""

    def __init__(
        self,
        known_tools: set[str] | frozenset[str],
        legacy_aliases: dict[str, str] | None = None,
        *,
        error_list_limit: int = 16,
    ) -> None:
        self._known = frozenset(known_tools) | frozenset(SKILL_IDS)
        self._aliases = dict(legacy_aliases or {})
        self._adapter = TypeAdapter(_ToolCall)
        self._error_list_limit = error_list_limit

    def validate(self, data: object) -> tuple[dict[str, Any] | None, str | None]:
        """Return (normalized_call, error); exactly one of the two is None."""
        try:
            call = self._adapter.validate_python(data)
        except ValidationError as exc:
            return None, self._format_error(exc)
        name = self._aliases.get(call.tool, call.tool)
        if name not in self._known:
            available = ", ".join(sorted(self._known)[: self._error_list_limit])
            return None, f"工具 {call.tool} 不存在，可用工具: {available}"
        return {"tool": name, "args": _coerce_scalars(call.args)}, None

    def _format_error(self, exc: ValidationError) -> str:
        parts: list[str] = []
        for error in exc.errors():
            loc = ".".join(str(part) for part in error["loc"]) or "调用"
            parts.append(f"{loc}: {error['msg']}")
        return "工具调用格式错误: " + "; ".join(parts)
