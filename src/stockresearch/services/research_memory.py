"""Search historical research reports (decision memory)."""

import json

from sqlalchemy.orm import Session

from stockresearch.core.schemas import MemorySearchHit, MemorySearchOut
from stockresearch.db.models import ResearchReport


def search_research_memory(
    db: Session,
    user_id: int,
    query: str,
    *,
    limit: int = 10,
) -> MemorySearchOut:
    q = query.strip().lower()
    if not q:
        return MemorySearchOut(query=query, hits=[])

    rows = (
        db.query(ResearchReport)
        .filter(ResearchReport.user_id == user_id)
        .order_by(ResearchReport.created_at.desc())
        .limit(200)
        .all()
    )
    hits: list[MemorySearchHit] = []
    for row in rows:
        payload = row.report_json if isinstance(row.report_json, dict) else {}
        summary = str(payload.get("summary", ""))
        haystack = " ".join(
            [
                row.symbol,
                row.name,
                summary,
                str(payload.get("bias", "")),
                json.dumps(payload, ensure_ascii=False),
            ]
        ).lower()
        if q not in haystack:
            continue
        hits.append(
            MemorySearchHit(
                report_id=row.id,
                symbol=row.symbol,
                name=row.name,
                bias=str(payload.get("bias", "neutral")),
                summary=summary[:300],
                composite_score=float(payload.get("composite_score", 0)),
                created_at=row.created_at,
            )
        )
        if len(hits) >= limit:
            break
    return MemorySearchOut(query=query, hits=hits)
