"""Glossary coverage tests."""

import json
from pathlib import Path


def test_glossary_has_minimum_coverage() -> None:
    path = Path(__file__).resolve().parents[2] / "src/stockresearch/data/glossary.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data) >= 80
