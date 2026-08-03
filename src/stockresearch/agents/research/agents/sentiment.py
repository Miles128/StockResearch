"""Sentiment dimension agent — isolated news/hot tools."""

from __future__ import annotations

from stockresearch.agents.research.agents._scoring import as_confidence
from stockresearch.agents.research.context import ResearchContext
from stockresearch.agents.research.dimension_text import REPORT_DIM_VOICE, finalize_dimension
from stockresearch.agents.research.react import DimensionAgent, ResearchTool
from stockresearch.core.constants import CONFIDENCE_LOW, CONFIDENCE_MEDIUM
from stockresearch.core.schemas import DimensionEvidence, DimensionResult
from stockresearch.data.providers.market import SentimentDataProvider
from stockresearch.utils.symbols import resolve_name

_SYSTEM = f"你是 A 股市场情绪分析师。{REPORT_DIM_VOICE}"


async def _tool_hot(ctx: ResearchContext) -> dict[str, object]:
    name = resolve_name(ctx.symbol)
    return await SentimentDataProvider().get_xueqiu_hot(ctx.symbol, name)


def _cluster_news_titles(items: list[object]) -> list[dict[str, object]]:
    """Merge near-duplicate titles into simple event clusters."""
    clusters: list[dict[str, object]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        key = title[:18]
        matched: dict[str, object] | None = None
        for cluster in clusters:
            seed = str(cluster.get("title", ""))
            if key and (key in seed or seed[:18] in title):
                matched = cluster
                break
        if matched is None:
            clusters.append(
                {
                    "title": title,
                    "count": 1,
                    "url": item.get("url"),
                    "source": item.get("source"),
                    "items": [item],
                }
            )
        else:
            matched["count"] = int(matched.get("count", 1)) + 1
            bucket = matched.get("items")
            if isinstance(bucket, list):
                bucket.append(item)
    return clusters


async def _tool_news(ctx: ResearchContext) -> dict[str, object]:
    name = resolve_name(ctx.symbol)
    news = await SentimentDataProvider().get_symbol_news(ctx.symbol, name)
    score = SentimentDataProvider().score_titles([item["title"] for item in news])
    budget = ctx.resolved_budget()
    clusters: list[dict[str, object]] = []
    if budget.news_cluster:
        clusters = _cluster_news_titles(list(news))

    cross_checks: list[dict[str, object]] = []
    if budget.news_deep_cross_check > 0:
        from stockresearch.data.providers.web_fetch import fetch_url_excerpt

        candidates = (
            clusters
            if clusters
            else [
                {
                    "title": n.get("title"),
                    "url": n.get("url"),
                    "source": n.get("source"),
                    "count": 1,
                }
                for n in news
                if isinstance(n, dict)
            ]
        )
        for cluster in candidates[: budget.news_deep_cross_check]:
            url = str(cluster.get("url") or "").strip()
            title = str(cluster.get("title") or "").strip()
            excerpt = ""
            if url:
                excerpt = await fetch_url_excerpt(url, max_chars=280)
            cross_checks.append(
                {
                    "title": title,
                    "url": url or None,
                    "source": cluster.get("source"),
                    "excerpt": excerpt,
                    "cluster_count": int(cluster.get("count", 1) or 1),
                }
            )

    return {
        "items": news,
        "news_score": score,
        "clusters": clusters,
        "cross_checks": cross_checks,
    }


def _build(data: dict[str, object], analysis: str) -> DimensionResult:
    hot = data["xueqiu_hot"]
    news = data["akshare_news"]
    assert isinstance(hot, dict)
    assert isinstance(news, dict)

    items = news.get("items", [])
    assert isinstance(items, list)
    news_score = float(news.get("news_score", 0))
    clusters = news.get("clusters") if isinstance(news.get("clusters"), list) else []
    cross_checks = news.get("cross_checks") if isinstance(news.get("cross_checks"), list) else []

    bull_ratio = float(hot.get("bull_ratio", 0.5))
    available = bool(hot.get("available", True))
    heat_score = int(hot.get("heat_score", 0))
    post_count = int(hot.get("post_count", 0))
    source = str(hot.get("source", "unknown"))

    score = 4.0 + bull_ratio * 6
    if news_score < -0.2:
        score -= 1.0
    if news_score > 0.2:
        score += 1.0
    if not available:
        score = max(1.0, min(10.0, score - 0.5))
    score = max(1.0, min(10.0, score))

    risks = ["情绪指标波动较大，需结合基本面"]
    if not available:
        risks.insert(0, "雪球/东财情绪数据未成功拉取，结论置信度降低")
    if news_score < -0.3:
        risks.insert(0, "近期新闻偏负面")
    if not items:
        risks.append("个股新闻为空，需核对数据源")

    fallback_highlight = (
        f"热度 {heat_score}、讨论 {post_count}、多空比 {bull_ratio:.0%}、新闻 {len(items)} 条"
        f"（来源 {source}）"
    )
    fallback_highlights = [fallback_highlight]
    if clusters:
        top = clusters[0] if isinstance(clusters[0], dict) else None
        if top:
            fallback_highlights.append(
                f"事件聚类：{str(top.get('title', ''))[:40]}（{int(top.get('count', 1))}条相近）"
            )
    if cross_checks:
        checked = sum(1 for c in cross_checks if isinstance(c, dict) and c.get("excerpt"))
        fallback_highlights.append(f"关键新闻交叉核对 {checked}/{len(cross_checks)} 条")

    has_data = available or bool(items)
    sources: list[str] = []
    if available:
        sources.append("xueqiu_hot")
    if items:
        sources.append("akshare_news")
    gaps: list[str] = []
    if not available:
        gaps.append("雪球/东财情绪未取到")
    else:
        note = str(hot.get("coverage_note") or "").strip()
        if note:
            gaps.append(note)
    if not items:
        gaps.append("个股新闻为空")

    evidence: list[DimensionEvidence] = []
    for check in cross_checks[:2]:
        if not isinstance(check, dict):
            continue
        title = str(check.get("title", "")).strip()
        excerpt = str(check.get("excerpt") or "").strip()
        snippet = excerpt[:120] if excerpt else title[:120]
        if not snippet:
            continue
        evidence.append(
            DimensionEvidence(
                source=str(check.get("source") or "news"),
                date=None,
                snippet=snippet,
                url=str(check.get("url") or "") or None,
                kind="other",
            )
        )
    if not evidence:
        for item in items[:2]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            evidence.append(
                DimensionEvidence(
                    source=str(item.get("source") or "news"),
                    date=None,
                    snippet=title[:120],
                    url=str(item.get("url") or "") or None,
                    kind="other",
                )
            )
    if available:
        evidence.append(
            DimensionEvidence(
                source=source,
                date=None,
                snippet=f"热度 {heat_score} · 多空比 {bull_ratio:.0%}",
                kind="other",
            )
        )

    return finalize_dimension(
        agent="sentiment",
        score=score,
        confidence=as_confidence(CONFIDENCE_MEDIUM if has_data else CONFIDENCE_LOW),
        raw_analysis=analysis,
        data_sources=sources,
        fallback_highlights=fallback_highlights,
        fallback_risks=risks,
        evidence=evidence[:4],
        gaps=gaps,
        partial=not available or not items,
    )


SENTIMENT_AGENT = DimensionAgent(
    agent_id="sentiment",
    label="情绪面",
    system_prompt=_SYSTEM,
    tools=(
        ResearchTool("xueqiu_hot", "雪球热度与多空比", _tool_hot),
        ResearchTool("akshare_news", "个股相关新闻", _tool_news),
    ),
    build=_build,
)
