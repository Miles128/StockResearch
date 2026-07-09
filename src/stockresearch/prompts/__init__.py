"""Load editable prompt templates from the prompts/ directory.

By default prompts are read from the project root ``prompts/`` directory.
If a prompt file is missing there, the built-in package prompts are used as
fallback. Set ``PROMPTS_DIR`` in ``.env`` to use a custom directory.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from stockresearch.core.config import get_settings

_PACKAGE_PROMPTS_DIR = Path(__file__).resolve().parent
_PACKAGE_MASTERS_DIR = _PACKAGE_PROMPTS_DIR / "masters"
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_EXTERNAL_DIR = _PROJECT_ROOT / "prompts"


def _external_prompts_dir() -> Path | None:
    """Return the configured external prompts directory, if it exists."""
    settings = get_settings()
    if settings.prompts_path is not None:
        return settings.prompts_path
    if _DEFAULT_EXTERNAL_DIR.is_dir():
        return _DEFAULT_EXTERNAL_DIR
    return None


def _resolve_prompt_path(relative_path: str) -> Path:
    """Prefer external prompts; fall back to built-in package prompts."""
    external = _external_prompts_dir()
    if external is not None:
        external_path = external / relative_path
        if external_path.is_file():
            return external_path
    return _PACKAGE_PROMPTS_DIR / relative_path


@lru_cache(maxsize=64)
def load_prompt(relative_path: str) -> str:
    """Load a prompt file relative to prompts/ (e.g. ``long_term_context.md``)."""
    path = _resolve_prompt_path(relative_path)
    return path.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=32)
def load_master_prompt(master_id: str) -> str:
    """Load a master persona prompt from prompts/masters/{id}.md."""
    external = _external_prompts_dir()
    if external is not None:
        external_path = external / "masters" / f"{master_id}.md"
        if external_path.is_file():
            return external_path.read_text(encoding="utf-8").strip()

    path = _PACKAGE_MASTERS_DIR / f"{master_id}.md"
    if not path.is_file():
        msg = f"Unknown built-in master prompt: {master_id}"
        raise FileNotFoundError(msg)
    return path.read_text(encoding="utf-8").strip()
