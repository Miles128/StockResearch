"""Shared phrasing for multi-agent prompts."""

AGENT_VOICE = (
    "以专业投研口径撰写 3～5 句话，引用上文具体数据与指标，"
    "表述客观、克制，禁止 markdown。不要建议买卖。"
)

DEBATE_VOICE = (
    "每轮严格两段：先写一行【摘要】1～2 句核心论点；"
    "再写【详述】2～4 句关键论据（援引数据、回应对方，禁止空话复述）。"
    "禁止 markdown。不要建议买卖。"
)

JUDGE_VOICE = (
    "以裁判口径说明结论、判定理由、分歧程度（大/中等/小）及分歧焦点。"
    "不要建议买卖。"
)

DEBATE_UTTERANCE_MAX = 220
JUDGE_FIELD_MAX = 180

DEBATE_ROUNDS = 3
