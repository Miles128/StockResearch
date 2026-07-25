"""Multi-symbol factor comparison (watchlist-friendly, no LLM)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from stockresearch.core.schemas import CompareRowOut, CompareTableOut, NumericFactorOut
from stockresearch.services.factors import compute_numeric_factors
from stockresearch.utils.symbols import resolve_name

logger = logging.getLogger(__name__)


async def build_compare_table(
    symbols: list[str],
    *,
    factor_keys: tuple[str, ...] | None = None,
) -> CompareTableOut:
    """Snapshot numeric factors for up to N symbols for side-by-side review."""
    cleaned: list[str] = []
    for raw in symbols:
        sym = str(raw).strip()
        if len(sym) == 6 and sym.isdigit() and sym not in cleaned:
            cleaned.append(sym)
        if len(cleaned) >= 12:
            break

    rows: list[CompareRowOut] = []
    for symbol in cleaned:
        name = resolve_name(symbol)
        try:
            factors, provenance = await compute_numeric_factors(
                symbol, factor_keys=factor_keys
            )
            rows.append(
                CompareRowOut(
                    symbol=symbol,
                    name=name,
                    factors=factors,
                    bars_adjust=provenance.adjust,
                    bars_source=provenance.source,
                    bars_as_of=provenance.as_of,
                    partial=provenance.partial or any(f.partial for f in factors),
                    note=provenance.note,
                )
            )
        except Exception as exc:
            logger.warning("compare factors failed for %s: %s", symbol, exc, exc_info=True)
            rows.append(
                CompareRowOut(
                    symbol=symbol,
                    name=name,
                    factors=[],
                    bars_adjust="none",
                    bars_source="",
                    bars_as_of=None,
                    partial=True,
                    note=f"因子计算失败：{exc}",
                )
            )

    return CompareTableOut(
        rows=rows,
        as_of=datetime.now(UTC).date().isoformat(),
        point_in_time=True,
        notes=[
            "对比表为当日因子快照（非历史截面回放）；缺数标 partial。",
            "用于自选池并排核对，不构成买卖建议。",
        ],
    )


def flatten_compare_csv(table: CompareTableOut) -> str:
    import csv
    import io

    keys: list[str] = []
    for row in table.rows:
        for f in row.factors:
            if f.key not in keys:
                keys.append(f.key)
    buf = io.StringIO()
    writer = csv.writer(buf)
    header = ["symbol", "name", "bars_adjust", "bars_source", "bars_as_of", "partial"] + keys
    writer.writerow(header)
    for row in table.rows:
        by_key = {f.key: f for f in row.factors}
        cells = [
            row.symbol,
            row.name,
            row.bars_adjust,
            row.bars_source,
            row.bars_as_of or "",
            "1" if row.partial else "0",
        ]
        for k in keys:
            f: NumericFactorOut | None = by_key.get(k)
            cells.append("" if f is None or f.value is None else f.value)
        writer.writerow(cells)
    return buf.getvalue()
