"""Shared phrasing for multi-agent prompts.

Voice constants no longer hardcode writing style — that is now controlled
by output_style.py's reading_mode (professional / friendly).  Instead,
these constants focus on *structural* constraints (length, format, banned
actions) that are mode-agnostic.

The actual writing-style rules are injected via `apply_style_to_system()`
in llm.py, which reads the current reading_mode from the ContextVar.
"""

# ── Agent voice: structural constraints only ──
AGENT_VOICE = (
    "撰写 3～5 句话，引用上文具体数据与指标，表述客观、克制，禁止 markdown。不要建议买卖。"
)
