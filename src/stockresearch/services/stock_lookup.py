"""Stock lookup — local fast path + LLM for unknown names; ambiguous asks user."""

import json
import re
from dataclasses import dataclass

from stockresearch.core.constants import NAME_TO_SYMBOL, SYMBOL_NAMES
from stockresearch.core.exceptions import ValidationError
from stockresearch.utils.llm import LLMClient, get_llm_client

_SYMBOL_IN_TEXT = re.compile(r"\d{6}")
_PUNCT_RE = re.compile(r"[，。！？、；：" "''（）().,!?;:'\" \\[\\]]+")
_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")

STOCK_ALIASES: dict[str, str] = {
    "茅台": "600519",
    "五粮": "000858",
    "宁德": "300750",
    "平安": "601318",
    "招行": "600036",
    "中芯": "688981",
    "中芯国际": "688981",
    "比亚迪": "002594",
    "招商证券": "600999",
    "中信证券": "600030",
    "中信": "600030",
    "徐工": "000425",
    "徐工机械": "000425",
}

_LLM_LOOKUP_SYSTEM = """你是 A 股股票识别助手。根据用户输入匹配股票。
只输出 JSON，不要其他文字。格式：
{"status":"confirmed","symbol":"600519","name":"贵州茅台"}
或 {"status":"ambiguous","candidates":[{"symbol":"601318","name":"中国平安"},{"symbol":"000001","name":"平安银行"}]}
或 {"status":"not_found"}
规则：
- 只有非常确定才用 confirmed
- 置信度不足、存在近义候选、或有两只以上合理可能 → 必须 ambiguous，在 candidates 列出 1–4 只（含你最倾向的）
- 无法识别 → not_found"""


@dataclass(frozen=True)
class StockCandidate:
    symbol: str
    name: str


@dataclass(frozen=True)
class StockLookupResult:
    status: str
    symbol: str | None
    name: str | None
    message: str
    candidates: tuple[StockCandidate, ...]
    normalized_query: str


def clean_stock_query(raw: str) -> str:
    text = raw.strip()
    if not text:
        return ""
    code_match = _SYMBOL_IN_TEXT.search(text)
    if code_match:
        return code_match.group(0)
    return _PUNCT_RE.sub("", text)


def _name_for(symbol: str, fallback: str) -> str:
    return SYMBOL_NAMES.get(symbol, fallback)


def _local_search(query: str) -> list[StockCandidate]:
    cleaned = clean_stock_query(query)
    if not cleaned:
        return []

    if re.fullmatch(r"\d{6}", cleaned):
        return [StockCandidate(cleaned, _name_for(cleaned, cleaned))]

    results: list[StockCandidate] = []
    seen: set[str] = set()

    def add(symbol: str, name: str) -> None:
        if symbol in seen:
            return
        seen.add(symbol)
        results.append(StockCandidate(symbol, name))

    if cleaned in NAME_TO_SYMBOL:
        symbol = NAME_TO_SYMBOL[cleaned]
        add(symbol, _name_for(symbol, cleaned))

    for name, symbol in NAME_TO_SYMBOL.items():
        if cleaned in name or name in cleaned:
            add(symbol, name)

    for alias, symbol in STOCK_ALIASES.items():
        if cleaned == alias or cleaned in alias or alias in cleaned:
            add(symbol, _name_for(symbol, alias))

    return results


def _catalog_hint() -> str:
    lines = [f"{sym} {name}" for sym, name in SYMBOL_NAMES.items()]
    lines.extend(f"{sym} {alias}" for alias, sym in STOCK_ALIASES.items())
    return "\n".join(lines)


def _parse_llm_lookup(raw_json: str) -> StockLookupResult | None:
    match = _JSON_BLOCK.search(raw_json)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

    status = str(data.get("status", ""))
    if status == "confirmed":
        symbol = str(data.get("symbol", "")).zfill(6)[-6:]
        name = str(data.get("name", symbol))
        if not re.fullmatch(r"\d{6}", symbol):
            return None
        c = StockCandidate(symbol, name)
        return StockLookupResult(
            status="confirmed",
            symbol=symbol,
            name=name,
            message=f"大模型识别：{name}（{symbol}）",
            candidates=(c,),
            normalized_query="",
        )
    if status == "ambiguous":
        candidates: list[StockCandidate] = []
        for item in data.get("candidates", []):
            sym = str(item.get("symbol", "")).zfill(6)[-6:]
            nm = str(item.get("name", sym))
            if re.fullmatch(r"\d{6}", sym):
                candidates.append(StockCandidate(sym, nm))
        if not candidates:
            return None
        preview = "、".join(f"{c.name}({c.symbol})" for c in candidates[:5])
        return StockLookupResult(
            status="ambiguous",
            symbol=None,
            name=None,
            message=f"大模型不确定，请确认：{preview}",
            candidates=tuple(candidates),
            normalized_query="",
        )
    if status == "not_found":
        return StockLookupResult(
            status="not_found",
            symbol=None,
            name=None,
            message="未识别到该股票，请检查名称或输入 6 位代码",
            candidates=(),
            normalized_query="",
        )
    return None


async def _llm_lookup(raw: str, client: LLMClient) -> StockLookupResult | None:
    user = f"用户输入：{raw}\n\n常见参考：\n{_catalog_hint()}\n\n也可识别任意有效 A 股 6 位代码。"
    text = await client.complete(_LLM_LOOKUP_SYSTEM, user)
    result = _parse_llm_lookup(text)
    if result and result.normalized_query == "":
        normalized = clean_stock_query(raw)
        return StockLookupResult(
            status=result.status,
            symbol=result.symbol,
            name=result.name,
            message=result.message,
            candidates=result.candidates,
            normalized_query=normalized or raw,
        )
    return result


def resolve_local(query: str) -> tuple[str, str]:
    raw = query.strip()
    if not raw:
        raise ValidationError("请输入股票代码或名称")
    normalized = clean_stock_query(raw)
    candidates = _local_search(normalized or raw)
    if len(candidates) == 1:
        return candidates[0].symbol, candidates[0].name
    if len(candidates) > 1:
        preview = "、".join(f"{c.name}({c.symbol})" for c in candidates[:3])
        raise ValidationError(f"匹配到多只，请确认：{preview}")
    if re.fullmatch(r"\d{6}", normalized or ""):
        sym = normalized or raw
        return sym, _name_for(sym, sym)
    raise ValidationError(f"未找到「{raw}」，请直接输入 6 位代码")


async def lookup_stock(query: str, llm: LLMClient | None = None) -> StockLookupResult:
    raw = query.strip()
    if not raw:
        raise ValidationError("请输入股票代码或名称")

    normalized = clean_stock_query(raw)
    candidates = _local_search(normalized or raw)

    if len(candidates) == 1:
        c = candidates[0]
        return StockLookupResult(
            status="confirmed",
            symbol=c.symbol,
            name=c.name,
            message=f"已匹配：{c.name}（{c.symbol}）",
            candidates=(c,),
            normalized_query=normalized or raw,
        )

    if len(candidates) > 1:
        preview = "、".join(f"{c.name}({c.symbol})" for c in candidates[:5])
        return StockLookupResult(
            status="ambiguous",
            symbol=None,
            name=None,
            message=f"匹配到多只，请确认：{preview}",
            candidates=tuple(candidates),
            normalized_query=normalized or raw,
        )

    client = llm or get_llm_client()
    llm_result = await _llm_lookup(raw, client)
    if llm_result is not None:
        return StockLookupResult(
            status=llm_result.status,
            symbol=llm_result.symbol,
            name=llm_result.name,
            message=llm_result.message,
            candidates=llm_result.candidates,
            normalized_query=normalized or raw,
        )

    return StockLookupResult(
        status="not_found",
        symbol=None,
        name=None,
        message=f"未找到「{raw}」，请直接输入 6 位股票代码",
        candidates=(),
        normalized_query=normalized or raw,
    )
