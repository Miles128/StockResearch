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


def _run_worker() -> None:
    import asyncio

    from stockresearch.worker import run_worker

    asyncio.run(run_worker())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stockresearch")
    subparsers = parser.add_subparsers(dest="command")

    api_parser = subparsers.add_parser("api", help="Run the FastAPI server")
    api_parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    api_parser.add_argument("--port", type=int, default=8000, help="Bind port")
    api_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    subparsers.add_parser("worker", help="Run the background scheduler worker")

    args = parser.parse_args(argv)
    if args.command == "api":
        _run_api(args.host, args.port, args.reload)
        return 0
    if args.command == "worker":
        _run_worker()
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
