"""Application-wide constants."""

DISCLAIMER = "以上内容由 AI 生成，仅供参考，不构成投资建议。"

INTENT_NEWS = "news"
INTENT_RESEARCH = "research"
INTENT_RISK = "risk"
INTENT_CHAT = "chat"
INTENT_COMPOSITE = "composite"

SENTIMENT_BULLISH = "bullish"
SENTIMENT_BEARISH = "bearish"
SENTIMENT_NEUTRAL = "neutral"

IMPACT_MAJOR = "major"
IMPACT_NORMAL = "normal"
IMPACT_NOISE = "noise"

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

SEVERITY_YELLOW = "yellow"
SEVERITY_RED = "red"
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"

# Known A-share symbol → name mapping for MVP
SYMBOL_NAMES: dict[str, str] = {
    "600519": "贵州茅台",
    "000858": "五粮液",
    "300750": "宁德时代",
    "601318": "中国平安",
    "600036": "招商银行",
    "688981": "中芯国际",
    "002594": "比亚迪",
    "601012": "隆基绿能",
    "600900": "长江电力",
    "000001": "平安银行",
    "600999": "招商证券",
    "000425": "徐工机械",
}

NAME_TO_SYMBOL: dict[str, str] = {v: k for k, v in SYMBOL_NAMES.items()}

SYMBOL_SECTORS: dict[str, str] = {
    "600519": "白酒",
    "000858": "白酒",
    "300750": "新能源",
    "601318": "券商",
    "600036": "银行",
    "688981": "半导体",
    "002594": "汽车",
    "601012": "新能源",
    "600900": "电力",
    "000001": "银行",
    "600999": "券商",
    "000425": "机械",
}

NEWS_BLACKLIST_KEYWORDS = ("暴涨", "惊爆", "疯涨", "血洗", "崩盘")

AVAILABLE_SECTORS: tuple[str, ...] = (
    "白酒",
    "新能源",
    "半导体",
    "医药",
    "银行",
    "地产",
    "军工",
    "消费",
    "计算机",
    "汽车",
    "电力",
    "煤炭",
    "钢铁",
    "券商",
    "机械",
    "有色金属",
    "传媒",
)
