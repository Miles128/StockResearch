"""跨端画线契约：Python 算法输出必须等于共享 fixture（chart_overlay_contract.json）。

该 fixture 同时被前端 chartOverlayContract.test.ts 断言——两端跑同一输入，
必须产出同一趋势线集合，否则视为算法漂移（PRD §9a/9b 同 schema 契约）。
"""

import json
from pathlib import Path

from stockresearch.services.chart_overlays import Bar, detect_trend_lines

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "chart_overlay_contract.json").read_text(encoding="utf-8")
)


def test_trend_lines_match_shared_fixture() -> None:
    bars = [
        Bar(date=b["date"], high=b["high"], low=b["low"], close=b["close"]) for b in FIXTURE["bars"]
    ]
    lines = detect_trend_lines(bars)
    assert len(lines) == len(FIXTURE["trend_lines"]), "line count drifted from frontend"

    def contract(line):
        return {
            "kind": line.kind,
            "slope_per_bar": round(line.slope_per_bar, 6),
            "end_price": round(line.end_price, 4),
            "touches": line.touches,
        }

    actual = sorted((contract(line) for line in lines), key=lambda c: (c["kind"], c["end_price"]))
    expected = sorted(
        (
            {k: v for k, v in c.items() if k != "start_index" and k != "end_index"}
            for c in FIXTURE["trend_lines"]
        ),
        key=lambda c: (c["kind"], c["end_price"]),
    )
    assert actual == expected


def test_fixture_has_support_and_resistance() -> None:
    kinds = {c["kind"] for c in FIXTURE["trend_lines"]}
    assert {"support", "resistance"} <= kinds, "fixture must exercise both sides"
