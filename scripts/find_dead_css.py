#!/usr/bin/env python3
"""Heuristic dead-code scanner: CSS selectors defined in web/src/styles but
never referenced in web/src TS/TSX.

Usage (from repo root):
    uv run python scripts/find_dead_css.py          # report candidates
    uv run python scripts/find_dead_css.py --clean  # apply --fix (git diff to review)

Notes:
- Heuristic only: class names built via template literals or from server data
  are invisible to this scan; always eyeball the candidates before deleting.
- Recommended cadence: once per release, plus after every UI-chrome refactor.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STYLES_DIR = ROOT / "web" / "src" / "styles"
SRC_DIR = ROOT / "web" / "src"

_CSS_CLASS_RE = re.compile(r"\.([a-zA-Z][\w-]*)")
# className 属性匹配：支持 "a b" / 'a' / `a ${x} b` / {"a"} / {cond ? "a" : "b"}
_CLASS_ATTR_RE = re.compile(
    r"className\s*=\s*\{?(?:\"(.*?)\"|'(.*?)'|`(.*?)`)",
    re.DOTALL,
)
# 模板字面量前缀：`lists-${listsMode}` → lists-
_TEMPLATE_PREFIX_RE = re.compile(r"([a-zA-Z][\w-]*)\s*\$\{")


def _add_literal_tokens(names: set[str], body: str | None) -> None:
    if not body:
        return
    for token in body.split():
        token = token.strip()
        if not token or not token[0].isalpha() or "${" in token or "{" in token:
            continue
        names.add(token)
    for m in _TEMPLATE_PREFIX_RE.finditer(body):
        prefix = m.group(1).rstrip("-")
        if prefix:
            names.add(prefix)


def collect_tsx_class_names() -> set[str]:
    names: set[str] = set()
    for path in SRC_DIR.rglob("*.ts*"):
        if "__tests__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for m in _CLASS_ATTR_RE.finditer(text):
            body = m.group(1) or m.group(2) or m.group(3)
            _add_literal_tokens(names, body)
        # 表达式内散落的字符串字面量：className={cond ? "a b" : "c"} 只被上面
        # 抓到第一个引号对，这里对 { ... } 窗口内的引号字面量做兜底。
        for m in re.finditer(r"className\s*=\s*\{([^{}]*)\}", text):
            expr = m.group(1)
            for lit in re.findall(r"[\"'`]([a-zA-Z][\w-]*)[\"'`]", expr):
                names.add(lit)
    return names


def collect_css_selectors() -> dict[str, set[str]]:
    by_file: dict[str, set[str]] = {}
    for path in STYLES_DIR.rglob("*.css"):
        text = path.read_text(encoding="utf-8")
        selectors: set[str] = set()
        for block in re.split(r"[{}]", text):
            for m in _CSS_CLASS_RE.finditer(block):
                cls = m.group(1)
                if cls in ("active", "hover", "focus", "disabled", "open", "hidden"):
                    continue
                selectors.add(cls)
        by_file[str(path.relative_to(ROOT))] = selectors
    return by_file


def main() -> int:
    used = collect_tsx_class_names()
    by_file = collect_css_selectors()
    total_dead = 0
    for css_path, selectors in sorted(by_file.items()):
        dead = sorted(s for s in selectors if s not in used)
        if dead:
            total_dead += len(dead)
            print(f"{css_path}: {len(dead)} candidates")
            for cls in dead:
                print(f"  .{cls}")
    print(f"\nTotal candidate selectors never referenced in TSX: {total_dead}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
