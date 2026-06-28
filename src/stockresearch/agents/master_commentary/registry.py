"""Master persona registry — built-in prompts from prompts/masters/ + user custom masters."""

from __future__ import annotations

import re

from stockresearch.agents.master_commentary.schemas import MasterCommentaryOut
from stockresearch.core.schemas import CustomMasterOut, ModeSettingsOut
from stockresearch.prompts import load_master_prompt

BUILTIN_MASTER_IDS: tuple[str, ...] = ("buffett", "munger", "burry")

BUILTIN_MASTER_NAMES: dict[str, str] = {
    "buffett": "沃伦·巴菲特",
    "munger": "查理·芒格",
    "burry": "迈克尔·伯里",
}

_MASTER_JSON_SCHEMA = """{
  "master": "<master_id>",
  "signal": "bullish|neutral|bearish",
  "confidence": 0.82,
  "reasoning": "用1-2句话说明观点",
  "key_metric": "最关注的核心指标或事实"
}"""

_CUSTOM_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


def validate_custom_master_id(master_id: str) -> str:
    cleaned = master_id.strip().lower()
    if not _CUSTOM_ID_RE.match(cleaned):
        msg = "自定义大师 ID 需为小写字母开头，仅含字母数字下划线，最长 32 字符"
        raise ValueError(msg)
    if cleaned in BUILTIN_MASTER_IDS:
        msg = f"ID {cleaned} 与内置大师冲突"
        raise ValueError(msg)
    return cleaned


def _custom_master_map(settings: ModeSettingsOut) -> dict[str, CustomMasterOut]:
    return {m.id: m for m in settings.custom_masters}


def resolve_master_ids(settings: ModeSettingsOut) -> list[str]:
    """Active master IDs respecting settings selection + custom entries."""
    selected = settings.selected_masters or list(BUILTIN_MASTER_IDS)
    custom_ids = {m.id for m in settings.custom_masters}
    out: list[str] = []
    for mid in selected:
        if mid in BUILTIN_MASTER_IDS or mid in custom_ids:
            if mid not in out:
                out.append(mid)
    if not out:
        out = list(BUILTIN_MASTER_IDS)
    return out


def get_master_config(
    master_id: str,
    settings: ModeSettingsOut,
) -> dict[str, str]:
    """Return {id, name, system} for a built-in or custom master."""
    custom = _custom_master_map(settings).get(master_id)
    if custom is not None:
        body = custom.system_prompt.strip()
        system = f"{body}\n\n请基于提供的投研摘要给出点评。只输出 JSON，禁止 markdown。\n{_MASTER_JSON_SCHEMA}"
        return {"id": custom.id, "name": custom.name, "system": system}

    if master_id in BUILTIN_MASTER_IDS:
        body = load_master_prompt(master_id)
        system = (
            f"{body}\n\n请基于提供的投研摘要，给出你对该标的的点评。"
            f"只输出 JSON，禁止 markdown。\n{_MASTER_JSON_SCHEMA.replace('<master_id>', master_id)}"
        )
        return {
            "id": master_id,
            "name": BUILTIN_MASTER_NAMES[master_id],
            "system": system,
        }

    msg = f"Unknown master: {master_id}"
    raise KeyError(msg)


def to_commentary_payload(
    result: MasterCommentaryOut,
    settings: ModeSettingsOut,
) -> dict[str, str | float]:
    """Serialize master commentary with resolved display name."""
    try:
        display_name = get_master_config(result.master, settings)["name"]
    except KeyError:
        display_name = result.master
    return {
        "master": result.master,
        "name": display_name,
        "signal": result.signal,
        "signal_text": result.signal_text,
        "confidence": result.confidence,
        "reasoning": result.reasoning,
        "key_metric": result.key_metric,
    }


def list_available_masters(settings: ModeSettingsOut) -> list[dict[str, str]]:
    """Catalog for settings UI."""
    items = [
        {"id": mid, "name": BUILTIN_MASTER_NAMES[mid], "builtin": "true"}
        for mid in BUILTIN_MASTER_IDS
    ]
    for custom in settings.custom_masters:
        items.append({"id": custom.id, "name": custom.name, "builtin": "false"})
    return items
