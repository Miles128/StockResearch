"""Read/write project root .env for local single-user configuration."""

from __future__ import annotations

import re
from pathlib import Path

_ENV_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def _sanitize_value(value: str) -> str:
    """Strip CR/LF and other control chars so a value cannot inject new keys.

    Prevents newline-injection (e.g. ``base_url="https://x\\nEVIL=1"``) that
    would otherwise append arbitrary variables to the .env file.
    """
    return "".join(ch for ch in value if ch.isprintable()).strip()


def resolve_env_path() -> Path:
    """Return .env path in the current working directory (project root when started locally)."""
    return Path.cwd() / ".env"


def read_env_map(path: Path | None = None) -> dict[str, str]:
    target = path or resolve_env_path()
    if not target.is_file():
        return {}
    result: dict[str, str] = {}
    for line in target.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _ENV_KEY_RE.match(stripped)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def write_env_vars(updates: dict[str, str], path: Path | None = None) -> Path:
    """Merge key=value pairs into .env, preserving comments and unrelated keys."""
    target = path or resolve_env_path()
    lines: list[str] = []
    if target.is_file():
        lines = target.read_text(encoding="utf-8").splitlines()
    else:
        example = target.parent / ".env.example"
        if example.is_file():
            lines = example.read_text(encoding="utf-8").splitlines()

    pending = {key: _sanitize_value(value) for key, value in updates.items()}
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            out.append(line)
            continue
        match = _ENV_KEY_RE.match(stripped)
        if match and match.group(1) in pending:
            key = match.group(1)
            out.append(f"{key}={pending.pop(key)}")
        else:
            out.append(line)

    for key, value in pending.items():
        out.append(f"{key}={value}")

    target.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    return target


def save_llm_env(
    *,
    api_key: str | None,
    base_url: str | None,
    model: str | None,
    use_mock: bool | None,
    keep_api_key_if_empty: bool = True,
) -> None:
    """Persist LLM settings to .env and clear settings cache."""
    from stockresearch.core.config import get_settings

    current = get_settings()
    key = (api_key or "").strip()
    if not key and keep_api_key_if_empty:
        key = current.llm_api_key.strip()

    updates: dict[str, str] = {}
    if key:
        updates["LLM_API_KEY"] = key
    elif not keep_api_key_if_empty:
        updates["LLM_API_KEY"] = ""

    if base_url is not None:
        updates["LLM_BASE_URL"] = base_url.strip()
    if model is not None:
        updates["LLM_MODEL"] = model.strip()
    if use_mock is not None:
        updates["USE_MOCK_LLM"] = "true" if use_mock else "false"

    write_env_vars(updates)
    get_settings.cache_clear()
