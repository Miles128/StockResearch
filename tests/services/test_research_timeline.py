"""Unit tests for same-symbol research timeline helpers."""

from datetime import UTC, datetime

from stockresearch.services.research_timeline import annotate_deltas, entry_from_payload, snapshot_factors


def test_snapshot_factors_keeps_known_keys() -> None:
    snaps = snapshot_factors(
        {
            "factors": [
                {"key": "momentum_20d", "label": "20日动量", "value": 5.2, "partial": False},
                {"key": "unknown_x", "label": "x", "value": 1},
                {"key": "pe_percentile", "label": "PE", "percentile": 0.3, "partial": True},
            ]
        }
    )
    assert [s.key for s in snaps] == ["momentum_20d", "pe_percentile"]
    assert snaps[0].value == 5.2
    assert snaps[1].percentile == 0.3
    assert snaps[1].partial is True


def test_annotate_deltas_marks_bias_and_score_change() -> None:
    a = entry_from_payload(
        report_id=1,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        payload={"bias": "bullish", "composite_score": 6.0, "summary": "first"},
    )
    b = entry_from_payload(
        report_id=2,
        created_at=datetime(2026, 2, 1, tzinfo=UTC),
        payload={"bias": "bearish", "composite_score": 4.5, "summary": "second"},
    )
    annotate_deltas([a, b])
    assert a.bias_changed is False
    assert a.score_delta is None
    assert b.bias_changed is True
    assert b.score_delta == -1.5


def test_entry_from_payload_trims_summary() -> None:
    entry = entry_from_payload(
        report_id=9,
        created_at=datetime(2026, 3, 1, tzinfo=UTC),
        payload={
            "bias": "neutral",
            "composite_score": 5,
            "analysis_depth": "deep",
            "summary": "x" * 200,
            "factor_alignment_note": "因子与结论大致同向",
        },
    )
    assert len(entry.summary) == 160
    assert entry.analysis_depth == "deep"
    assert entry.factor_alignment_note is not None
