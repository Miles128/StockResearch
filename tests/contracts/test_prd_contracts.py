"""PRD 契约测试 — 固化 §二/§4.1/§五/§七 的关键契约，防止接线回归。

原则：每条契约 = 一个可读断言；不依赖网络/LLM；失败即 PRD 契约破裂。
"""

from __future__ import annotations

from stockresearch.agents.market.research_stream import run_market_research_stream
from stockresearch.services.user_preferences import _coerce_mode_settings


def test_research_mode_defaults_debate_on() -> None:
    """PRD §二：research 模式辩论默认开（未显式设置时）。"""
    settings = _coerce_mode_settings({"mode": "research"})
    assert settings.enable_debate is True
    assert settings.enable_glossary is False


def test_research_mode_explicit_debate_off_respected() -> None:
    """用户显式关闭辩论时，research 模式不得覆盖。"""
    settings = _coerce_mode_settings({"mode": "research", "enable_debate": False})
    assert settings.enable_debate is False


def test_advisor_mode_debate_stays_off() -> None:
    """PRD §二：个人模式辩论默认关。"""
    settings = _coerce_mode_settings({"mode": "advisor"})
    assert settings.enable_debate is False


def test_standard_reading_mode_normalized_to_friendly() -> None:
    """PRD §11.0：存量 standard 档归一为 friendly。"""
    settings = _coerce_mode_settings({"mode": "advisor", "reading_mode": "standard"})
    assert settings.reading_mode == "friendly"


def test_analysis_depth_defaults_by_mode() -> None:
    """PRD §4.1：advisor→standard，research→comprehensive。"""
    advisor = _coerce_mode_settings({"mode": "advisor"})
    research = _coerce_mode_settings({"mode": "research"})
    assert advisor.analysis_depth == "standard"
    assert research.analysis_depth == "comprehensive"


def test_market_research_stream_honors_depth_signature() -> None:
    """PRD §4.1：市场研究流必须接受并解析 analysis_depth（不恒为 standard）。"""
    import inspect

    sig = inspect.signature(run_market_research_stream)
    assert "analysis_depth" in sig.parameters
    from stockresearch.agents.market.research_stream import resolve_analysis_depth

    assert resolve_analysis_depth(explicit="deep", settings_depth="standard") == "deep"


def test_industry_research_stream_honors_depth_signature() -> None:
    """PRD §4.1：行业研究流同契约。"""
    import inspect

    from stockresearch.agents.industry.stream import run_industry_research_stream

    sig = inspect.signature(run_industry_research_stream)
    assert "analysis_depth" in sig.parameters


def test_price_alert_scheduler_uses_asia_shanghai_wall_clock() -> None:
    """PRD §七：调度器墙钟逻辑必须与 cron 同一时区（Asia/Shanghai）。"""
    from stockresearch.services.price_alert_scheduler import _TZ

    assert str(_TZ) == "Asia/Shanghai"


def test_margin_total_keeps_single_unit() -> None:
    """PRD §5.3：融资融券 total_balance 必须同单位（元），禁止混加股数。"""
    from stockresearch.data.providers.market import chips

    source = open(chips.__file__, encoding="utf-8").read()
    # SSE 分支必须优先取元计价列（融券余量金额/融券余额），不得直接加 融券余量
    assert "融券余量金额" in source or "融券余额" in source
    assert "融资余额" in source


def test_scheduler_zoneinfo_shanghai_everywhere() -> None:
    """PRD §七：briefing/daily-bar 调度器与告警一致使用 Asia/Shanghai。"""
    import inspect

    from stockresearch.services import briefing_scheduler, daily_bar_scheduler

    for mod in (briefing_scheduler, daily_bar_scheduler):
        src = inspect.getsource(mod)
        assert "Asia/Shanghai" in src


def test_cache_hit_marks_terms_inside_output_style_scope() -> None:
    """PRD §11.1/§四：缓存命中路径必须走 output_style_scope（尊重 glossary 设置）。"""
    import inspect

    from stockresearch.api.routes import research

    src = inspect.getsource(research.analyze_stock)
    assert "output_style_scope(" in src
    assert "custom_glossary" in src


def test_plan_execute_prompt_braces_escaped() -> None:
    """PRD §八 Phase 2：plan_execute 提示词 JSON 大括号必须转义（防 KeyError）。"""
    import inspect

    from stockresearch.agents.orchestrator import plan_execute

    src = inspect.getsource(plan_execute)
    assert "{tools_block}" in src
    # 示例 JSON 的花括号必须转义为 {{ }}，不能裸 { 当替换字段
    assert '{{"id": 1' in src


def test_debate_prompts_converged_on_voice_factories() -> None:
    """辩论 prompt 必须收敛到 voice.py 工厂，禁止各域复制文本（防漂移）。"""
    import inspect

    from stockresearch.agents import industry, market
    from stockresearch.agents.research import battle, debate

    for mod in (debate, market.research_stream, industry.stream):
        src = inspect.getsource(mod)
        assert 'bull_system("' in src, f"{mod.__name__} 未使用 bull_system 工厂"
        assert 'bear_system("' in src, f"{mod.__name__} 未使用 bear_system 工厂"

    # judge 唯一事实源在 voice.py；battle 层不允许再内联裁判文本
    battle_src = inspect.getsource(battle)
    assert "research_judge_system" in battle_src
    assert '"bias"' not in battle_src.split("iter_battle_events")[0]


def test_debate_sync_and_stream_share_judge_format() -> None:
    """sync/stream 裁判必须共用同一 JSON 格式与解析器（PRD §二 同一管线）。"""
    import inspect

    from stockresearch.agents.research import debate

    src = inspect.getsource(debate)
    assert "research_judge_system()" in src
    assert "ResearchJudgeOut.from_llm" in src
    assert "_JUDGE_SYSTEM" not in src


def test_market_analysis_queries_route_to_4d_research() -> None:
    """大盘分析性问法 → 市场四维投研；纯报价问法 → 轻量路径。"""
    from stockresearch.agents.orchestrator.complexity import wants_market_research as w

    assert w("今天大盘怎么样") is True
    assert w("A股市场走势如何") is True
    assert w("大盘为什么涨") is True
    assert w("上证指数展望") is True
    assert w("今天大盘多少点") is False
    assert w("上证指数现在多少") is False
    assert w("有什么财经新闻") is False
    assert w("帮我分析一下600519") is False


def test_chat_execute_wires_market_research_route() -> None:
    """chat_execute 必须优先于 trend 轻量路径路由市场四维投研。"""
    import inspect

    from stockresearch.agents.orchestrator import chat_execute

    src = inspect.getsource(chat_execute._run_react_sync)
    assert "wants_market_research" in src
    assert "_run_market_research_sync" in src


def test_predictions_persist_on_report_save() -> None:
    """Phase 12a：研报持久化必须自动留存预测记录（幂等）。"""
    import inspect

    from stockresearch.api.routes import research

    src = inspect.getsource(research.persist_report)
    assert "register_report_verifications" in src
    src2 = inspect.getsource(research.register_report_verifications)
    assert "record_prediction_for_report" in src2


def test_prediction_scoring_is_pit_disciplined() -> None:
    """Phase 12a：评分只用预测之后的 qfq 日线（PIT）。"""
    import inspect

    from stockresearch.services import prediction_journal

    src = inspect.getsource(prediction_journal._score_one)
    assert "created_at" in src
    assert "due_at > date.today()" in src
