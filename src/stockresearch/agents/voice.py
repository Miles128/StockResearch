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

# ── Debate voice: structural format ──
DEBATE_VOICE = (
    "每轮严格两段：先写一行【摘要】1～2 句核心论点；"
    "再写【详述】2～4 句关键论据（援引数据、回应对方，禁止空话复述）。"
    "禁止 markdown。不要建议买卖。"
)

# ── Judge voice: structural format ──
JUDGE_VOICE = "以裁判口径说明结论、判定理由、分歧程度（大/中等/小）及分歧焦点。不要建议买卖。"

DEBATE_UTTERANCE_MAX = 220
JUDGE_FIELD_MAX = 180

DEBATE_ROUNDS = 3


# ── 辩论 prompt 工厂：所有域（个股/大盘/行业）共用同一结构，仅角色名与
# 域内要点不同。此前 debate/market/industry 各复制一份 bull/bear/judge
# 文本并已漂移；此处为唯一事实源。 ──
def bull_system(domain: str, extra: str = "") -> str:
    """A 股看多分析师 system prompt（domain: 如「A 股」「A 股大盘」「A 股板块」）。"""
    extra_block = f"\n{extra}" if extra else ""
    return (
        f"你是{domain}看多分析师（Bull Agent）。\n{DEBATE_VOICE} {extra_block}\n不要给出买入建议。"
    )


def bear_system(domain: str, extra: str = "") -> str:
    """A 股看空分析师 system prompt。"""
    extra_block = f"\n{extra}" if extra else ""
    return (
        f"你是{domain}看空分析师（Bear Agent）。\n{DEBATE_VOICE} {extra_block}\n不要给出卖出建议。"
    )


def research_judge_system() -> str:
    """投研裁判 system prompt（JSON 输出，配合 ResearchJudgeOut.from_llm 解析）。

    个股/大盘/行业辩论共用；不要再复制该文本。
    """
    return (
        f"你是投研裁判。{JUDGE_VOICE} 只输出 JSON，禁止 markdown。\n"
        '{{"bias":"偏多|偏空|中性","summary":"结论，2句内","reason":"为何如此判，2句内",'
        '"divergence":"分歧大|分歧中等|分歧小","divergence_point":"分歧焦点，1句"}}'
    )
