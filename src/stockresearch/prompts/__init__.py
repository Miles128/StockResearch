"""Load editable prompt templates from the prompts/ directory."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent
_MASTERS_DIR = _PROMPTS_DIR / "masters"


@lru_cache(maxsize=64)
def load_prompt(relative_path: str) -> str:
    """Load a prompt file relative to prompts/ (e.g. ``long_term_context.md``)."""
    path = _PROMPTS_DIR / relative_path
    return path.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=32)
def load_master_prompt(master_id: str) -> str:
    """Load a built-in master persona prompt from prompts/masters/{id}.md."""
    path = _MASTERS_DIR / f"{master_id}.md"
    if not path.is_file():
        msg = f"Unknown built-in master prompt: {master_id}"
        raise FileNotFoundError(msg)
    return path.read_text(encoding="utf-8").strip()
