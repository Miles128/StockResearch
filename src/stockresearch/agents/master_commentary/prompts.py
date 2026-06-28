"""Backward-compatible exports for master commentary prompts."""

from stockresearch.agents.master_commentary.registry import (
    BUILTIN_MASTER_IDS,
    BUILTIN_MASTER_NAMES,
    get_master_config,
    list_available_masters,
    resolve_master_ids,
)

__all__ = [
    "BUILTIN_MASTER_IDS",
    "BUILTIN_MASTER_NAMES",
    "get_master_config",
    "list_available_masters",
    "resolve_master_ids",
]
