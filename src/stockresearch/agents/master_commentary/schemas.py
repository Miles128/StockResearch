"""Structured output for master commentary."""

from typing import Literal

from pydantic import BaseModel, Field

from stockresearch.agents.structured_output import extract_json_dict


class MasterCommentaryOut(BaseModel):
    master: str = Field(description="大师 ID")
    signal: Literal["bullish", "neutral", "bearish"] = "neutral"
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    reasoning: str = ""
    key_metric: str = ""

    @property
    def signal_text(self) -> str:
        return {"bullish": "偏多", "neutral": "中性", "bearish": "偏空"}[self.signal]

    @classmethod
    def from_llm(cls, master_id: str, raw: str) -> "MasterCommentaryOut":
        data = extract_json_dict(raw)
        if data:
            signal = str(data.get("signal", "neutral")).lower()
            if signal not in ("bullish", "neutral", "bearish"):
                signal = _normalize_signal(signal)
            try:
                confidence = float(data.get("confidence", 0.5))
            except (ValueError, TypeError):
                confidence = 0.5
            return cls(
                master=master_id,
                signal=signal,  # type: ignore[arg-type]
                confidence=max(0.0, min(1.0, confidence)),
                reasoning=str(data.get("reasoning", "")).strip() or str(data.get("reason", "")).strip(),
                key_metric=str(data.get("key_metric", "")).strip() or str(data.get("keyMetric", "")).strip(),
            )
        return cls(master=master_id, reasoning=raw.strip()[:200])


def _normalize_signal(text: str) -> Literal["bullish", "neutral", "bearish"]:
    lowered = text.lower()
    if "偏多" in text or "bullish" in lowered or "看多" in text or "buy" in lowered:
        return "bullish"
    if "偏空" in text or "bearish" in lowered or "看空" in text or "sell" in lowered:
        return "bearish"
    return "neutral"
