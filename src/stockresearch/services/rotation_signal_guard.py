"""Rotation signal guard: ensure rotation claims carry a directional label.

When the model mentions sector/style/capital rotation without telling the user
whether the signal is bullish, bearish, or neutral, this guard appends a clear
caution so personal-version readers are not left guessing.
"""

from __future__ import annotations

import re

# Phrases that describe rotation but may omit a directional signal.
_ROTATION_TERMS = re.compile(
    r"板块轮动|轮动效应|风格切换|资金切换|龙头切换|"
    r"板块切换|风格轮动|资金轮动|行业轮动|高低切换"
)

# Directional/signal words that satisfy the requirement.
_SIGNAL_WORDS = re.compile(
    r"偏多|偏空|中性|看多|看空|乐观|谨慎|积极|消极|"
    r"利好|利空|上涨|下跌|看涨|看跌|看多信号|看空信号|"
    r" bullish| bearish| bullish| bearish"
)

_SENTENCE_SPLIT = re.compile(r"([。！？\n]+)")

_HINT = "（该判断未明确偏多/偏空/中性信号，请谨慎参考）"


def ensure_rotation_signals(text: str) -> str:
    """Append a caution to rotation sentences that lack a directional label.

    The guard works sentence-by-sentence so it only touches the relevant
    clause and leaves other content unchanged.
    """
    if not text:
        return text

    parts = _SENTENCE_SPLIT.split(text)
    out: list[str] = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            sentence = part
            if _ROTATION_TERMS.search(sentence) and not _SIGNAL_WORDS.search(sentence):
                sentence = sentence.rstrip() + _HINT
            out.append(sentence)
        else:
            out.append(part)
    return "".join(out)
