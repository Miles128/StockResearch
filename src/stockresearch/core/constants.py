"""Application-wide constants."""

DISCLAIMER = "以上内容由 AI 生成，仅供参考，不构成投资建议。"

INTENT_NEWS = "news"
INTENT_RESEARCH = "research"
INTENT_RISK = "risk"
INTENT_CHAT = "chat"
INTENT_COMPOSITE = "composite"
INTENT_MARKET = "market"

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
    "600030": "中信证券",
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

# Layer-1: title contains any keyword → discard (ingest + feed)
NEWS_BLACKLIST_KEYWORDS: tuple[str, ...] = (
    # 极端行情煽动
    "暴涨",
    "惊爆",
    "疯涨",
    "血洗",
    "崩盘",
    "狂飙",
    "闪崩",
    "跳水",
    "跌停潮",
    "涨停潮",
    # 震惊体 / 情绪煽动
    "震惊",
    "太猛了",
    "太恐怖",
    "惊现",
    "罕见一幕",
    "炸锅",
    "刷屏",
    "全网沸腾",
    "万人空巷",
    "不敢看",
    "吓人",
    "亮了",
    "绝了",
    "跪了",
    "哭了",
    "史诗级",
    "教科书级",
    # 荐股 / 诱导交易
    "明天涨停",
    "赶紧买",
    "快上车",
    "错过后悔",
    "最后一波",
    "干就完了",
    "冲就完了",
    "财富自由",
    "一夜暴",
    "百倍",
    "千倍",
    "连板王",
    "妖股",
    "必涨",
    "稳赚",
    "包赚",
)

# Layer-1a: heavy demotion keywords → discard (same as blacklist)
NEWS_HEAVY_REJECT_KEYWORDS: tuple[str, ...] = (
    "揭秘",
    "内幕",
    "真相",
    "背后",
    "必看",
    "速看",
    "千万别",
    "警惕",
    "重大信号",
    "刚刚",
    "紧急",
    "火速",
)

# Layer-1b: medium/light demotion — keyword → rank multiplier (0–1)
NEWS_DEMOTION_KEYWORDS: dict[str, float] = {
    # 中降权：泛化解读 / 汇总类
    "解读": 0.70,
    "一文看懂": 0.70,
    "盘点": 0.70,
    "梳理": 0.75,
    "汇总": 0.75,
    "速递": 0.70,
    "快评": 0.75,
    "十大": 0.70,
    "全面": 0.75,
    "深度": 0.80,
    "传闻": 0.75,
    "据传": 0.75,
    "消息人士": 0.70,
    # 轻降权：不确定性 / 前瞻措辞（保留但略降优先级）
    "或将": 0.85,
    "有望": 0.85,
    "疑似": 0.80,
    "或迎": 0.85,
    "关注": 0.90,
    "留意": 0.90,
    "提醒": 0.88,
    "前瞻": 0.88,
    "展望": 0.88,
}

# Layer-2 source authority (prefix match on NewsItem.source)
NEWS_SOURCE_AUTHORITY: dict[str, float] = {
    "新华社": 1.0,
    "人民日报": 1.0,
    "财联社": 0.95,
    "证券时报": 0.92,
    "上海证券报": 0.92,
    "中国证券报": 0.92,
    "巨潮": 0.9,
    "交易所": 0.9,
    "证监会": 0.9,
    "华尔街见闻": 0.88,
    "第一财经": 0.85,
    "东方财富": 0.78,
    "同花顺": 0.75,
    "雪球": 0.7,
    "新浪": 0.68,
    "腾讯": 0.68,
    "博查": 0.6,
    "博查搜索": 0.6,
    "default": 0.55,
}

# Output banned patterns for neutral_guard: (regex, replacement)
# replacement=None means delete the matched text entirely
# PRD §9.1: 建议买入/卖出 allowed (with disclaimer in UI); 加仓/减仓/持有观望 forbidden.
OUTPUT_BANNED_PATTERNS: tuple[tuple[str, str | None], ...] = (
    (r"持有观望", "仓位适中"),
    (r"建议\s*加仓", "建议控制仓位"),
    (r"建议\s*减仓", "建议控制仓位"),
    (r"加仓", "仓位偏低"),
    (r"减仓", "仓位偏高"),
    (r"目标价\s*[\d.]+", "合理估值区间"),
    (r"(强烈|坚决)\s*(推荐|建议)", "值得关注"),
    (r"赶紧|立即|马上|务必", None),
)

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
