"""Card merge helpers shared by sync and streaming orchestrators."""


def merge_plan_cards(
    plan_cards: list[dict[str, object]],
    tool_cards: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Attach research/news/etc. cards produced by tools during Plan-Execute."""
    merged: list[dict[str, object]] = list(plan_cards)
    for card in tool_cards:
        ctype = card.get("type")
        if ctype == "research":
            merged = [c for c in merged if c.get("type") != "research"]
            merged.append(card)
        elif ctype in ("news", "financial", "market"):
            if not any(c.get("type") == ctype for c in merged):
                merged.append(card)
    return merged
