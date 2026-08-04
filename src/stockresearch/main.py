"""CLI entrypoint for StockResearch."""

from __future__ import annotations

import argparse
import sys


def _run_api(host: str, port: int, reload: bool) -> None:
    import uvicorn

    uvicorn.run(
        "stockresearch.api.app:app",
        host=host,
        port=port,
        reload=reload,
    )


def _run_worker() -> int:
    import asyncio

    from stockresearch.worker import run_worker

    return asyncio.run(run_worker())


def main(argv: list[str] | None = None) -> int:
    from stockresearch.cli.research_tools import register_research_cli, run_research_cli

    parser = argparse.ArgumentParser(prog="stockresearch")
    subparsers = parser.add_subparsers(dest="command")

    api_parser = subparsers.add_parser("api", help="Run the FastAPI server")
    api_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host (defaults to localhost; pass 0.0.0.0 only behind a trusted reverse proxy)",
    )
    api_parser.add_argument("--port", type=int, default=8000, help="Bind port")
    api_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    subparsers.add_parser("worker", help="Run the background scheduler worker")
    register_research_cli(subparsers)

    args = parser.parse_args(argv)
    if args.command == "api":
        _run_api(args.host, args.port, args.reload)
        return 0
    if args.command == "worker":
        return _run_worker()
    if args.command == "research":
        return run_research_cli(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
