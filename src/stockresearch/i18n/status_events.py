"""Structured SSE status events — frontend resolves message_key via i18n."""

from __future__ import annotations

from typing import Any


def status_event(key: str, **params: Any) -> dict[str, object]:
    """Emit a status event with an i18n key and optional interpolation params."""
    return {
        "type": "status",
        "message_key": key,
        "message_params": params,
    }
