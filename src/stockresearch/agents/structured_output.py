"""Pydantic parsers for LLM JSON outputs — replaces ad-hoc regex extraction."""

import json
import re
from typing import Literal, TypeVar

from pydantic import BaseModel, Field, ValidationError

_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")
_BIAS_TOKENS = ("偏多", "偏空", "中性")
_VOTE_TOKENS = _BIAS_TOKENS
T = TypeVar("T", bound=BaseModel)


def extract_json_dict(raw: str) -> dict[str, object] | None:
    match = _JSON_BLOCK.search(raw)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _normalize_bias(text: str) -> Literal["偏多", "偏空", "中性"]:
    lowered = text.lower()
    if "偏多" in text or "bullish" in lowered or "看多" in text:
        return "偏多"
    if "偏空" in text or "bearish" in lowered or "看空" in text:
        return "偏空"
    for token in _BIAS_TOKENS:
        if token in text:
            return token  # type: ignore[return-value]
    return "中性"


def _normalize_divergence(text: str) -> Literal["分歧大", "分歧中等", "分歧小"]:
    if "分歧大" in text:
        return "分歧大"
    if "分歧小" in text:
        return "分歧小"
    if "分歧中等" in text or "中等" in text:
        return "分歧中等"
    return "分歧中等"


class ResearchJudgeOut(BaseModel):
    bias: Literal["偏多", "偏空", "中性"] = "中性"
    summary: str = ""
    reason: str = ""
    divergence: Literal["分歧大", "分歧中等", "分歧小"] = "分歧中等"
    divergence_point: str = ""

    @property
    def final_bias(self) -> Literal["bullish", "bearish", "neutral"]:
        if self.bias == "偏多":
            return "bullish"
        if self.bias == "偏空":
            return "bearish"
        return "neutral"

    @classmethod
    def from_llm(cls, raw: str) -> "ResearchJudgeOut":
        data = extract_json_dict(raw)
        if data:
            try:
                bias = _normalize_bias(str(data.get("bias", "中性")))
                divergence = _normalize_divergence(str(data.get("divergence", "分歧中等")))
                summary = str(data.get("summary", "")).strip()
                reason = str(data.get("reason", "")).strip()
                divergence_point = str(data.get("divergence_point", "")).strip()
                if summary:
                    return cls(
                        bias=bias,
                        summary=summary,
                        reason=reason or summary,
                        divergence=divergence,
                        divergence_point=divergence_point or "多空对短期方向仍有分歧",
                    )
            except ValidationError:
                pass
        plain = raw.strip()
        bias = _normalize_bias(raw)
        return cls(
            bias=bias,
            summary=plain or "综合看，倾向中性。",
            reason=plain or "四维信号未形成一致方向。",
            divergence="分歧中等",
            divergence_point="估值与动量方向不完全一致",
        )


class VoteLabelOut(BaseModel):
    vote: Literal["偏多", "偏空", "中性"] = Field(default="中性")

    @classmethod
    def from_llm(cls, raw: str) -> "VoteLabelOut":
        for token in _VOTE_TOKENS:
            if token in raw:
                return cls(vote=token)  # type: ignore[arg-type]
        return cls()
