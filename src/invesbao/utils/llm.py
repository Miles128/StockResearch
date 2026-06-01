"""LLM client with mock fallback for tests."""

import json
import logging
import re
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import httpx

from invesbao.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str) -> str:
        pass

    async def stream_complete(self, system: str, user: str) -> AsyncIterator[str]:
        text = await self.complete(system, user)
        if text:
            yield text


class MockLLMClient(LLMClient):
    async def stream_complete(self, system: str, user: str) -> AsyncIterator[str]:
        text = await self.complete(system, user)
        step = 24
        for offset in range(0, len(text), step):
            yield text[offset : offset + step]

    async def complete(self, system: str, user: str) -> str:
        if "意图识别" in system:
            if any(kw in user for kw in ("风险", "止损", "仓位", "体检", "回撤")):
                if any(kw in user for kw in ("分析", "研究")):
                    return '{"intent": "composite", "symbols": [], "confidence": "high"}'
                return '{"intent": "risk", "symbols": [], "confidence": "high"}'
            if any(kw in user for kw in ("新闻", "快讯", "怎么了", "发生", "消息")):
                return '{"intent": "news", "symbols": [], "confidence": "high"}'
            if any(kw in user for kw in ("分析", "研究", "值不值得", "怎么样", "看看")):
                return '{"intent": "research", "symbols": [], "confidence": "high"}'
            return '{"intent": "chat", "symbols": [], "confidence": "high"}'
        if "翻译成人话" in system or "风控助手" in system:
            return "请您留意该持仓波动，做好止损纪律。"
        if "市场环境" in system:
            return "市场震荡，请您关注持仓板块政策变化。"
        if "相关性" in system:
            return "持仓行业较集中，请您留意联动风险。"
        if "风险叙述" in system:
            return "整体风险中等，请您关注回撤与集中度。"
        if "情景" in system:
            return "政策收紧 | 板块或承压\n流动性收紧 | 波动或加大"
        if "风控" in user or "risk" in system.lower():
            return "请您关注持仓波动，保持止损纪律。"
        if "摘要" in system or "一句话" in system:
            return "该消息可能对相关板块产生短期情绪影响，需关注后续政策落地。"
        if "基本面" in system:
            return (
                "亮点：营收稳健增长；毛利率维持高位；现金流健康。"
                "风险：估值处于历史中位；行业竞争加剧；商誉占比需关注。"
            )
        if "技术面" in system:
            return "短期均线多头排列，MACD 金叉，支撑位在成本价下方 5% 附近。"
        if "情绪" in system:
            return "社交媒体讨论热度中等，整体情绪偏中性略乐观。"
        if "筹码" in system:
            return "北向资金近期小幅净流入，龙虎榜未见明显游资出货迹象。"
        if "A 股股票识别" in system:
            query_line = user.split("\n", 1)[0]
            if query_line.startswith("用户输入："):
                query = query_line.removeprefix("用户输入：").strip()
            else:
                query = query_line.strip()
            if "茅台" in query:
                return '{"status":"confirmed","symbol":"600519","name":"贵州茅台"}'
            if "招商证券" in query or query == "招商":
                return '{"status":"confirmed","symbol":"600999","name":"招商证券"}'
            if "徐工" in query:
                return '{"status":"confirmed","symbol":"000425","name":"徐工机械"}'
            if "银行" in query and "招商" not in query:
                return (
                    '{"status":"ambiguous","candidates":['
                    '{"symbol":"600036","name":"招商银行"},'
                    '{"symbol":"000001","name":"平安银行"}]}'
                )
            if re.fullmatch(r"\d{6}", query):
                return f'{{"status":"confirmed","symbol":"{query}","name":"{query}"}}'
            return '{"status":"not_found"}'
        if "只输出一个词" in system:
            if "看多" in system:
                return "偏多"
            if "看空" in system:
                return "偏空"
            return "中性"
        if "激进风控 Agent" in system:
            return (
                "告警显示组合最大回撤约 8%，行业集中度 45%，仍处可控区间。"
                "龙头基本面未见明显恶化，波动更多来自板块轮动，系统性风险有限。"
                "激进视角下结构性机会仍可关注，但须严格执行止损纪律。"
            )
        if "中性风控 Agent" in system:
            return (
                "回撤预警与基本面亮点并存，信号方向并不一致。"
                "激进派或低估集中度风险，审慎派或高估短期波动影响。"
                "中性视角建议维持观望，待告警收敛或方向进一步明朗后再评估。"
            )
        if "审慎风控 Agent" in system:
            return (
                "组合行业集中度偏高，部分持仓距成本价回撤已接近预警阈值。"
                "若板块出现回调，缺乏有效对冲，回撤或由可控转为需处置。"
                "审慎视角下应以防守为先，优先处理集中度与止损纪律。"
            )
        if "看多 Agent" in system or "Bull Agent" in system:
            return (
                "基本面评分 7/10，营收保持增长；筹码面主力近五个交易日净流入。"
                "空方强调估值压力，但业绩增速已在部分消化溢价。"
                "中期偏多逻辑仍成立，短期波动不改趋势判断。"
            )
        if "看空 Agent" in system or "Bear Agent" in system:
            return (
                "技术面评分 6/10，RSI 偏高；情绪面尚未形成一致乐观预期。"
                "多方将基本面亮点外推为趋势延续，动量指标已现走弱迹象。"
                "上行空间受限，短期回撤风险仍需纳入评估。"
            )
        if "Research Manager" in system and "投研负责人" in system:
            return (
                '{"investment_thesis":"四维整体中性，缺乏一致方向。",'
                '"key_risk":"估值与动量背离","debate_summary":"多空各执一词",'
                '"recommended_bias":"中性"}'
            )
        if "Research Manager" in system:
            return "三方分歧主要在集中度与波动，建议您保持纪律、控制仓位。"
        if "投研裁判" in system:
            return (
                '{"bias":"中性","summary":"综合四维看，短期缺少明确单边动力。",'
                '"reason":"基本面与技术面信号互相抵消，情绪面未形成一致预期。",'
                '"divergence":"分歧中等","divergence_point":"估值与动量方向不一致"}'
            )
        if "风控裁判 Agent" in system or (
            "裁判 Agent" in system and "position_action" in system
        ):
            holdings = re.findall(r"(\S+)\((\d{6})\)", user)
            if not holdings:
                holdings = [("宁德时代", "300750")]
            holding_actions: list[dict[str, str]] = []
            for idx, (name, symbol) in enumerate(holdings):
                if idx == 0:
                    holding_actions.append(
                        {
                            "symbol": symbol,
                            "name": name,
                            "action": "减仓",
                            "reason": f"{name} 告警或回撤相对突出，建议优先控仓。",
                            "priority": "高",
                        }
                    )
                elif idx == 1:
                    holding_actions.append(
                        {
                            "symbol": symbol,
                            "name": name,
                            "action": "持有观望",
                            "reason": f"{name} 信号中性，暂以观望为主。",
                            "priority": "中",
                        }
                    )
                else:
                    holding_actions.append(
                        {
                            "symbol": symbol,
                            "name": name,
                            "action": "暂不调整",
                            "reason": f"{name} 暂无优先处置信号，维持现有仓位观察。",
                            "priority": "低",
                        }
                    )
            payload = {
                "analysis_process": (
                    "1. 对照规则引擎告警，识别回撤、黑天鹅与集中度暴露。\n"
                    "2. 结合市场、相关性与情景分析，评估组合联动风险。\n"
                    "3. 吸收三方辩论与 Research Manager 意见，逐股形成处置优先级。"
                ),
                "risk_level": "中",
                "position_action": "持有观望",
                "holding_actions": holding_actions,
                "summary": f"您当前 {len(holdings)} 只持仓整体风险可控，优先处理告警较突出的标的。",
                "reason": "激进派看到结构性机会，审慎派强调集中度与波动，需分股处置。",
                "divergence": "分歧中等",
            }
            return json.dumps(payload, ensure_ascii=False)
        if "乐观风控 Agent" in system or "乐观派" in system:
            return "整体回撤仍可控，龙头基本面尚可，但需您留意板块波动。"
        if "审慎风控 Agent" in system or "审慎派" in system:
            return "集中度与波动仍需您留意，单一行业回调可能拖累组合。"
        if "看多 Agent" in system:
            return "四维评分尚可，基本面与筹码提供中期支撑，但估值仍压制上行空间。"
        if "看空 Agent" in system:
            return "技术面动量偏弱，情绪未企稳，短期回撤风险仍不能忽视。"
        if "裁判 Agent" in system and "风控" in system:
            return (
                '{"risk_level":"中","position_action":"持有观望",'
                '"summary":"建议您先观望控仓",'
                '"reason":"有集中度预警，请您谨慎",'
                '"divergence":"分歧中等"}'
            )
        if "投小宝" in system or "投研助手" in system:
            return (
                "您好，感谢您的提问。简要来说，当前信息仍有限，建议您结合自己的投资纪律审慎看待。"
                f"\n\n以上内容由 AI 生成，仅供参考，不构成投资建议。"
            )
        return "您好，以上仅供参考，请您结合自己的判断决策。"


class OpenAICompatibleClient(LLMClient):
    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.llm_api_key
        self._base_url = settings.llm_base_url.rstrip("/")
        self._model = settings.llm_model

    async def stream_complete(self, system: str, user: str) -> AsyncIterator[str]:
        if not self._api_key:
            logger.warning("LLM API key missing, falling back to mock")
            mock = MockLLMClient()
            async for chunk in mock.stream_complete(system, user):
                yield chunk
            return

        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.3,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield str(content)

    async def complete(self, system: str, user: str) -> str:
        parts: list[str] = []
        async for chunk in self.stream_complete(system, user):
            parts.append(chunk)
        return "".join(parts)


def get_llm_client() -> LLMClient:
    if get_settings().use_mock_llm:
        return MockLLMClient()
    return OpenAICompatibleClient()
