"""Normalize composite research conclusions to a target character band."""

from __future__ import annotations

_PUNCT = ("。", "；", "！", "？", ".", ";")


def _compress_to_max(plain: str, max_len: int) -> str:
    if len(plain) <= max_len:
        return plain
    slice_ = plain[:max_len]
    for punct in _PUNCT:
        idx = slice_.rfind(punct)
        if idx >= int(max_len * 0.55):
            return plain[: idx + 1]
    return f"{plain[: max_len - 1]}…"


def _join_parts(parts: list[str]) -> str:
    cleaned = [p.strip().rstrip("。") for p in parts if p and p.strip()]
    if not cleaned:
        return ""
    text = "。".join(cleaned)
    return text if text.endswith("。") else f"{text}。"


def normalize_summary(
    text: str,
    *,
    min_len: int = 120,
    max_len: int = 180,
    expand_parts: list[str] | None = None,
) -> str:
    """Compress or expand summary text into [min_len, max_len] when possible."""
    plain = " ".join(text.split()).strip()
    if not plain:
        return plain

    if min_len <= len(plain) <= max_len:
        return plain

    if len(plain) > max_len:
        return _compress_to_max(plain, max_len)

    parts = [plain.rstrip("。")]
    seen = {plain}

    for raw in expand_parts or []:
        hint = raw.strip().rstrip("。")
        if not hint or hint in seen:
            continue
        seen.add(hint)
        candidate = _join_parts([*parts, hint])
        if min_len <= len(candidate) <= max_len:
            return candidate
        if len(candidate) > max_len:
            return _compress_to_max(candidate, max_len)
        parts.append(hint)

    result = _join_parts(parts) or plain
    return result if result.endswith("。") or not result else f"{result}。"
