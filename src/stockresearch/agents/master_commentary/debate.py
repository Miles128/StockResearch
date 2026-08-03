"""Cross-master debate — after individual commentaries, masters rebut each other."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from stockresearch.agents.master_commentary.registry import to_commentary_payload
from stockresearch.agents.master_commentary.schemas import MasterCommentaryOut
from stockresearch.core.schemas import ModeSettingsOut
from stockresearch.utils.llm import LLMClient

logger = logging.getLogger(__name__)

_DEBATE_SYSTEM = """你是投资观点辩论主持。多位大师已对同一标的给出独立点评，请组织一轮简短交锋。

输入为各位大师的 JSON 点评。输出 JSON（不要 markdown）：
{
  "rounds": [
    {"master": "<id>", "name": "<显示名>", "point": "核心立场一句", "rebuttal": "对其他观点的回应一句"}
  ],
  "consensus": "共识一句",
  "divergence": "最大分歧一句"
}

规则：每位大师仅一轮；rebuttal 须引用至少一位其他大师的分歧；禁止买卖建议。"""


async def stream_master_debate(
    llm: LLMClient,
    subject: str,
    commentaries: list[MasterCommentaryOut],
    *,
    settings: ModeSettingsOut,
) -> AsyncIterator[dict[str, Any]]:
    """Yield debate_start, per-master debate_round, debate_done."""
    if len(commentaries) < 2:
        return

    yield {
        "type": "master_debate_start",
        "subject": subject,
        "masters": [c.master for c in commentaries],
    }

    lines = []
    for c in commentaries:
        payload = to_commentary_payload(c, settings)
        lines.append(
            f"- {payload['name']}({c.master}): {c.signal_text} — {c.reasoning} [关注: {c.key_metric}]"
        )
    user_block = f"标的：{subject}\n\n" + "\n".join(lines)

    try:
        raw = await llm.complete(_DEBATE_SYSTEM, user_block)
        data = json.loads(raw.strip())
    except Exception as exc:
        logger.warning("Master debate failed: %s", exc)
        yield {
            "type": "master_debate_done",
            "subject": subject,
            "consensus": "大师观点未能完成交叉辩论",
            "divergence": str(exc),
            "rounds": [],
        }
        return

    rounds = data.get("rounds") if isinstance(data.get("rounds"), list) else []
    for i, rnd in enumerate(rounds, start=1):
        if not isinstance(rnd, dict):
            continue
        yield {
            "type": "master_debate_round",
            "round": i,
            "master": rnd.get("master", ""),
            "name": rnd.get("name", ""),
            "point": rnd.get("point", ""),
            "rebuttal": rnd.get("rebuttal", ""),
        }

    yield {
        "type": "master_debate_done",
        "subject": subject,
        "consensus": str(data.get("consensus", "")),
        "divergence": str(data.get("divergence", "")),
        "rounds": rounds,
    }
