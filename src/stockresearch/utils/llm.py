"""LLM client with mock fallback for tests."""

import json
import logging
import re
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import httpx

from stockresearch.core.config import get_settings

logger = logging.getLogger(__name__)


def _httpx_client_kwargs() -> dict:
    """Build httpx.AsyncClient kwargs for LLM calls.

    trust_env=False ignores shell HTTP_PROXY/HTTPS_PROXY (often breaks local dev
    when a stale proxy is set). Use LLM_HTTP_PROXY in .env when a proxy is required.
    """
    kwargs: dict = {
        "timeout": float(get_settings().llm_timeout_seconds),
        "trust_env": False,
    }
    proxy = get_settings().llm_http_proxy
    if proxy:
        kwargs["proxy"] = proxy
    return kwargs

from stockresearch.agents.output_style import apply_style_to_system
from stockresearch.core.exceptions import LLMConfigError
from stockresearch.core.llm_config import LlmOverrides, resolve_chat_completions_url
from stockresearch.utils.llm_usage import estimate_tokens, record_usage


def _styled_system(system: str) -> str:
    return apply_style_to_system(system)


class LLMClient(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str) -> str:
        pass

    async def complete_messages(self, messages: list[dict[str, str]]) -> str:
        """Complete with full message history. Default: concatenate into system+user."""
        system = messages[0]["content"] if messages and messages[0].get("role") == "system" else ""
        user_parts = []
        for m in messages:
            if m.get("role") == "system":
                continue
            role = m.get("role", "user")
            user_parts.append(f"[{role}]\n{m['content']}")
        return await self.complete(system, "\n".join(user_parts))

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

    def _mock_stock_skill_args(self, user: str) -> dict[str, object] | None:
        sym = re.search(r"\d{6}", user)
        if sym:
            return {"symbol": sym.group()}
        if "茅台" in user:
            return {"symbol": "600519"}
        last_user = user.rsplit("[user]", 1)[-1].strip() if "[user]" in user else user
        first_line = last_user.split("\n", 1)[0].strip()
        if any(kw in first_line for kw in ("分析", "研究", "看看", "怎么样", "值不值得")):
            return {"query": first_line or last_user.split("\n", 1)[-1].strip()}
        return None

    async def complete_messages(self, messages: list[dict[str, str]]) -> str:
        system = ""
        user = ""
        for m in messages:
            role = m.get("role")
            if role == "system":
                system = str(m.get("content", ""))
            elif role == "user":
                user = str(m.get("content", ""))
        return await self.complete(system, user)

    def _mock_reply(self, system: str, user: str) -> str:
        if "编排 Agent" in system or "调用工具" in system:
            skill_args = self._mock_stock_skill_args(user)
            if skill_args and any(
                kw in user
                for kw in (
                    "分析",
                    "研究",
                    "投研",
                    "四维",
                    "看看",
                    "怎么样",
                    "值不值得",
                    "茅台",
                    "600519",
                    "宁德",
                )
            ):
                return (
                    "```tool\n"
                    f'{{"tool": "skill_stock_research", "args": {json.dumps(skill_args, ensure_ascii=False)}}}\n'
                    "```\n"
                    '```tool\n{"tool": "reply", "args": {"message": "投研分析已完成，请见下方卡片与过程详情。\\n\\n以上内容由 AI 生成，仅供参考，不构成投资建议。"}}\n```'
                )
            if any(kw in user for kw in ("新闻", "快讯", "消息", "资讯", "公告", "报道")):
                sym_match = re.search(r"\d{6}", user)
                if sym_match:
                    sym = sym_match.group()
                    return (
                        f'```tool\n{{"tool": "get_news", "args": {{"symbol": "{sym}"}}}}\n```\n'
                        '```tool\n{"tool": "reply", "args": {"message": "已结合相关快讯完成新闻解读。\\n\\n以上内容由 AI 生成，仅供参考，不构成投资建议。"}}\n```'
                    )
                return (
                    '```tool\n{"tool": "get_news", "args": {}}\n```\n'
                    '```tool\n{"tool": "reply", "args": {"message": "已为您获取最新快讯并完成解读。\\n\\n以上内容由 AI 生成，仅供参考，不构成投资建议。"}}\n```'
                )
            if any(kw in user for kw in ("大盘", "市场", "股市", "走势", "行情", "板块")):
                return (
                    '```tool\n{"tool": "get_market_data", "args": {}}\n```\n'
                    '```tool\n{"tool": "reply", "args": {"message": "当前大盘震荡，建议您关注政策面变化。\\n\\n以上内容由 AI 生成，仅供参考，不构成投资建议。"}}\n```'
                )
            return (
                '```tool\n{"tool": "reply", "args": {"message": "您好，我是 StockResearch，专注A股投研分析。请问有什么金融投资方面的问题可以帮您？\\n\\n以上内容由 AI 生成，仅供参考，不构成投资建议。"}}\n```'
            )
        if "意图识别" in system:
            if any(kw in user for kw in ("大盘", "市场", "股市", "走势", "行情", "板块", "A股")):
                sectors = []
                for sec in ("半导体", "新能源", "白酒", "银行", "医药"):
                    if sec in user:
                        sectors.append(sec)
                return json.dumps({"intent": "market", "symbols": [], "sectors": sectors, "confidence": "high"})
            if any(kw in user for kw in ("风险", "止损", "仓位", "体检", "回撤")):
                if any(kw in user for kw in ("分析", "研究")):
                    return '{"intent": "composite", "symbols": [], "confidence": "high"}'
                return '{"intent": "risk", "symbols": [], "confidence": "high"}'
            if any(kw in user for kw in ("新闻", "快讯", "怎么了", "发生", "消息")):
                return '{"intent": "news", "symbols": [], "confidence": "high"}'
            if any(kw in user for kw in ("分析", "研究", "投研", "四维", "值不值得", "怎么样", "看看")):
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
        if "持仓简报" in system or "简报编辑" in system:
            return (
                '{"summary":"今日持仓整体震荡，涨跌互现；相关新闻以行业政策与龙头业绩为主，'
                '大盘指数小幅波动，北向资金方向需继续观察。",'
                '"sections":[{"title":"持仓表现","content":"主要持仓今日涨跌不一，'
                '浮动盈亏变化不大，需关注单日波动较大的个股。"},'
                '{"title":"新闻脉络","content":"持仓相关新闻偏中性；行业层面有政策与景气讨论；'
                '市场要闻集中在宏观流动性与指数表现。"},'
                '{"title":"综合结论","content":"短线以跟踪持仓波动与新闻落地为主，'
                '暂未见单一方向性信号；若大盘延续震荡，宜控制仓位集中度。"}]}'
            )
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
            if "平安" in query:
                return (
                    '{"status":"ambiguous","candidates":['
                    '{"symbol":"601318","name":"中国平安"},'
                    '{"symbol":"000001","name":"平安银行"}]}'
                )
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
                            "action": "仓位偏高",
                            "reason": f"{name} 告警或回撤相对突出，建议优先控制仓位。",
                            "priority": "高",
                        }
                    )
                elif idx == 1:
                    holding_actions.append(
                        {
                            "symbol": symbol,
                            "name": name,
                            "action": "仓位适中",
                            "reason": f"{name} 信号中性，暂以观察为主。",
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
                "position_action": "仓位适中",
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
                '{"risk_level":"中","position_action":"仓位适中",'
                '"summary":"建议您先观望控仓",'
                '"reason":"有集中度预警，请您谨慎",'
                '"divergence":"分歧中等"}'
            )
        if "StockResearch" in system or "投研助手" in system:
            return (
                "您好，感谢您的提问。简要来说，当前信息仍有限，建议您结合自己的投资纪律审慎看待。"
                "\n\n以上内容由 AI 生成，仅供参考，不构成投资建议。"
            )
        return "您好，以上仅供参考，请您结合自己的判断决策。"

    async def complete(self, system: str, user: str) -> str:
        system = _styled_system(system)
        text = self._mock_reply(system, user)
        record_usage(
            prompt_tokens=estimate_tokens(f"{system}\n{user}"),
            completion_tokens=estimate_tokens(text),
            is_estimate=True,
        )
        return text


class OpenAICompatibleClient(LLMClient):
    def __init__(self, overrides: LlmOverrides | None = None) -> None:
        cfg = overrides or LlmOverrides()
        self._api_key = cfg.effective_api_key()
        self._base_url = resolve_chat_completions_url(cfg.effective_base_url())
        self._model = cfg.effective_model()
        self._temperature = cfg.effective_temperature()

    async def stream_complete(self, system: str, user: str) -> AsyncIterator[str]:
        system = _styled_system(system)
        if not self._api_key:
            # 用户已显式请求真实 LLM（USE_MOCK_LLM=false）但未配置 API key，
            # 不再静默回退到 Mock，避免误以为"AI 回复质量差"。
            raise LLMConfigError(
                "LLM API key is not configured. Set USE_MOCK_LLM=true for offline "
                "development or provide a valid API key in Settings."
            )

        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self._temperature,
            "stream": True,
        }
        prompt_text = f"{system}\n{user}"
        completion_parts: list[str] = []
        usage_from_api: dict[str, int] | None = None
        async with httpx.AsyncClient(**_httpx_client_kwargs()) as client:
            async with client.stream(
                "POST",
                self._base_url,
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
                    raw_usage = chunk.get("usage")
                    if isinstance(raw_usage, dict) and raw_usage.get("total_tokens"):
                        usage_from_api = {
                            "prompt_tokens": int(raw_usage.get("prompt_tokens") or 0),
                            "completion_tokens": int(raw_usage.get("completion_tokens") or 0),
                        }
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        piece = str(content)
                        completion_parts.append(piece)
                        yield piece
        if usage_from_api:
            record_usage(
                prompt_tokens=usage_from_api["prompt_tokens"],
                completion_tokens=usage_from_api["completion_tokens"],
            )
        else:
            record_usage(
                prompt_tokens=estimate_tokens(prompt_text),
                completion_tokens=estimate_tokens("".join(completion_parts)),
                is_estimate=True,
            )

    async def complete(self, system: str, user: str) -> str:
        parts: list[str] = []
        async for chunk in self.stream_complete(system, user):
            parts.append(chunk)
        return "".join(parts)

    async def complete_messages(self, messages: list[dict[str, str]]) -> str:
        """Complete with full message history using the chat API natively."""
        styled_messages = list(messages)
        for idx, msg in enumerate(styled_messages):
            if msg.get("role") == "system" and msg.get("content"):
                styled_messages[idx] = {
                    **msg,
                    "content": _styled_system(str(msg["content"])),
                }
        if not self._api_key:
            raise LLMConfigError(
                "LLM API key is not configured. Set USE_MOCK_LLM=true for offline "
                "development or provide a valid API key in Settings."
            )

        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self._model,
            "messages": styled_messages,
            "temperature": self._temperature,
        }
        async with httpx.AsyncClient(**_httpx_client_kwargs()) as client:
            resp = await client.post(
                self._base_url,
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            content = str(data["choices"][0]["message"]["content"])
            usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
            if usage.get("total_tokens"):
                record_usage(
                    prompt_tokens=int(usage.get("prompt_tokens") or 0),
                    completion_tokens=int(usage.get("completion_tokens") or 0),
                )
            else:
                prompt_text = "\n".join(
                    f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages
                )
                record_usage(
                    prompt_tokens=estimate_tokens(prompt_text),
                    completion_tokens=estimate_tokens(content),
                    is_estimate=True,
                )
            return content


def get_llm_client(overrides: LlmOverrides | None = None) -> LLMClient:
    cfg = overrides or LlmOverrides()
    if cfg.effective_use_mock():
        return MockLLMClient()
    return OpenAICompatibleClient(cfg)
