"""Local CLI for research verify/export (no trading). Jupyter/MCP-friendly JSON stdout."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from stockresearch.core.schemas import ResearchReportOut
from stockresearch.db.models import ResearchReport, User
from stockresearch.db.session import SessionLocal, init_db
from stockresearch.services.compare_table import build_compare_table
from stockresearch.services.hypothesis_verify import HYPOTHESIS_PRESETS, verify_hypothesis
from stockresearch.services.report_export import report_to_csv, report_to_json, report_to_markdown
from stockresearch.services.research_timeline import compute_research_timeline

if TYPE_CHECKING:
    import argparse

    from sqlalchemy.orm import Session


def _resolve_user_id(db: Session, user_id: int | None) -> int:
    if user_id is not None:
        return user_id
    row = db.query(User).order_by(User.id.asc()).first()
    if row is None:
        raise SystemExit("数据库中无用户；请先通过 Web/API 登录一次。")
    return int(row.id)


def _print_json(payload: object) -> int:
    text = (
        payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, indent=2)
    )
    sys.stdout.write(text if text.endswith("\n") else text + "\n")
    return 0


async def _cmd_timeline(args: argparse.Namespace) -> int:
    init_db()
    with SessionLocal() as db:
        uid = _resolve_user_id(db, args.user_id)
        out = await compute_research_timeline(
            db,
            uid,
            args.symbol,
            include_post_hoc=not args.no_post_hoc,
            limit=args.limit,
        )
        return _print_json(out.model_dump(mode="json"))


async def _cmd_hypothesis(args: argparse.Namespace) -> int:
    if args.list_presets:
        return _print_json(HYPOTHESIS_PRESETS)
    out = await verify_hypothesis(args.symbol, rule=args.rule, lookback_days=args.lookback)
    return _print_json(out.model_dump(mode="json"))


async def _cmd_compare(args: argparse.Namespace) -> int:
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    out = await build_compare_table(symbols)
    return _print_json(out.model_dump(mode="json"))


async def _cmd_export(args: argparse.Namespace) -> int:
    init_db()
    with SessionLocal() as db:
        uid = _resolve_user_id(db, args.user_id)
        row = (
            db.query(ResearchReport)
            .filter(ResearchReport.id == args.report_id, ResearchReport.user_id == uid)
            .one_or_none()
        )
        if row is None:
            raise SystemExit(f"报告不存在: id={args.report_id}")
        report = ResearchReportOut.model_validate(row.report_json)
        if args.format == "json":
            body = report_to_json(report)
        elif args.format == "csv":
            body = report_to_csv(report)
        else:
            body = report_to_markdown(report)
        if args.out:
            Path(args.out).write_text(body, encoding="utf-8")
            sys.stdout.write(f"wrote {args.out}\n")
            return 0
        return _print_json(body)


def register_research_cli(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    research = subparsers.add_parser(
        "research",
        help="Research verify/export tools (timeline, hypothesis, compare, export)",
    )
    rsub = research.add_subparsers(dest="research_cmd", required=True)

    tl = rsub.add_parser("timeline", help="Same-symbol research replay timeline")
    tl.add_argument("symbol", help="6-digit A-share code")
    tl.add_argument("--user-id", type=int, default=None)
    tl.add_argument("--limit", type=int, default=20)
    tl.add_argument("--no-post-hoc", action="store_true")
    tl.set_defaults(handler=_cmd_timeline)

    hyp = rsub.add_parser("hypothesis", help="One-click hypothesis verify on qfq bars")
    hyp.add_argument("symbol", nargs="?", help="6-digit A-share code")
    hyp.add_argument("--rule", default="momentum_positive")
    hyp.add_argument("--lookback", type=int, default=240)
    hyp.add_argument("--list-presets", action="store_true")
    hyp.set_defaults(handler=_cmd_hypothesis)

    cmp_ = rsub.add_parser("compare", help="Factor compare table for symbols")
    cmp_.add_argument("symbols", help="Comma-separated 6-digit codes")
    cmp_.set_defaults(handler=_cmd_compare)

    exp = rsub.add_parser("export", help="Export a saved research report")
    exp.add_argument("report_id", type=int)
    exp.add_argument("--format", choices=("json", "csv", "md"), default="json")
    exp.add_argument("--user-id", type=int, default=None)
    exp.add_argument("--out", default=None, help="Optional output path")
    exp.set_defaults(handler=_cmd_export)


def run_research_cli(args: argparse.Namespace) -> int:
    handler = getattr(args, "handler", None)
    if handler is None:
        return 1
    if args.research_cmd == "hypothesis" and not args.list_presets and not args.symbol:
        raise SystemExit("hypothesis 需要 symbol，或使用 --list-presets")
    return asyncio.run(handler(args))
