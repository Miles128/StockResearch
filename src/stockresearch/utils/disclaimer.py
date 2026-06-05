"""Strip inline disclaimers from agent outputs — shown once per research turn in UI."""

import re

_PATTERNS = (
    re.compile(
        r"以下内容由\s*AI\s*生成[，,]\s*仅供参考[，,]\s*不构成投资建议[。.]?\s*",
        re.IGNORECASE,
    ),
    re.compile(
        r"以上内容由\s*AI\s*生成[，,]\s*仅供参考[，,]\s*不构成投资建议[。.]?\s*",
        re.IGNORECASE,
    ),
    re.compile(
        r"本产品所有\s*AI\s*输出仅供学习参考[，,]\s*不构成投资建议[。.]?\s*",
        re.IGNORECASE,
    ),
)


def strip_disclaimer(text: str) -> str:
    if not text:
        return ""
    result = text
    for pattern in _PATTERNS:
        result = pattern.sub("", result)
    return result.strip()
