"""Lightweight research card viewpoints derived from dimension evidence."""

from stockresearch.core.schemas import DimensionResult


def _join_lines(items: list[str]) -> str | None:
    cleaned = [item.strip() for item in items if item.strip()]
    if not cleaned:
        return None
    return "；".join(cleaned)


def _first_highlight(dim: DimensionResult | None) -> str | None:
    if dim is None:
        return None
    return _join_lines(dim.highlights)


def _first_risk_line(dimensions: dict[str, DimensionResult]) -> str | None:
    for key in ("fundamental", "technical", "sentiment", "chips"):
        dim = dimensions.get(key)
        if dim is None:
            continue
        joined = _join_lines(dim.risks)
        if joined:
            return joined
    return None


def build_viewpoints(
    dimensions: dict[str, DimensionResult],
    *,
    news_text_factor: str | None = None,
) -> dict[str, str]:
    """Map research dimensions to PRD lightweight card viewpoint keys."""
    _ = news_text_factor
    viewpoints: dict[str, str] = {}
    for key in ("fundamental", "technical", "sentiment", "chips"):
        line = _first_highlight(dimensions.get(key))
        if line:
            viewpoints[key] = line

    risk_line = _first_risk_line(dimensions)
    if risk_line:
        viewpoints["risk"] = risk_line
    return viewpoints
