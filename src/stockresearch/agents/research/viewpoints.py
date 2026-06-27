"""Lightweight research card viewpoints derived from dimension evidence."""

from stockresearch.core.schemas import DebateResult, DimensionResult


def _clip(text: str, limit: int = 120) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _first_highlight(dim: DimensionResult | None) -> str | None:
    if dim is None:
        return None
    for item in dim.highlights:
        if item.strip():
            return _clip(item)
    return None


def _first_risk_line(dimensions: dict[str, DimensionResult], debate: DebateResult | None) -> str | None:
    if debate and debate.consensus.strip():
        return _clip(debate.consensus)
    for dim in dimensions.values():
        for risk in dim.risks:
            if risk.strip():
                return _clip(risk)
    return None


def build_viewpoints(
    dimensions: dict[str, DimensionResult],
    debate: DebateResult | None,
    *,
    news_text_factor: str | None = None,
) -> dict[str, str]:
    """Map research dimensions to PRD lightweight card viewpoint keys."""
    viewpoints: dict[str, str] = {}
    for key in ("fundamental", "technical", "sentiment", "chips"):
        line = _first_highlight(dimensions.get(key))
        if line:
            viewpoints[key] = line

    if news_text_factor and news_text_factor.strip():
        snippet = news_text_factor.strip().splitlines()[0]
        if snippet:
            viewpoints.setdefault("sentiment", _clip(snippet))

    risk_line = _first_risk_line(dimensions, debate)
    if risk_line:
        viewpoints["risk"] = risk_line
    return viewpoints
