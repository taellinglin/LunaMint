"""Command line interface for lunamint."""
from __future__ import annotations

import argparse
import os
from typing import Optional

from lunamint.server import serve


def _set_sd_api_url(sd_api: Optional[str]) -> None:
    if not sd_api:
        return
    os.environ["SD_API_BASE_URL"] = sd_api
    os.environ["SD_API_URL"] = sd_api


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lunamint", description="Lunamint CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    server_parser = subparsers.add_parser("server", help="Start the EisenScript API server")
    server_parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    server_parser.add_argument("--port", type=int, default=4242, help="Bind port")
    server_parser.add_argument(
        "--sd-api",
        dest="sd_api",
        default=None,
        help="Optional SD API base URL (sets SD_API_BASE_URL)",
    )

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "server":
        _set_sd_api_url(args.sd_api)
        serve(args.host, args.port)
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
