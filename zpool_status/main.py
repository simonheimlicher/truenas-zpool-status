"""CLI entry point for zstat."""

from __future__ import annotations

import sys

from zpool_status.status import enrich_status, get_zpool_status


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] == "status":
        pool = args[1] if len(args) > 1 else None
        raw = get_zpool_status(pool)
        enriched = enrich_status(raw)
        sys.stdout.write(enriched)
    else:
        print(f"Unknown command: {args[0]}", file=sys.stderr)  # noqa: T201
        print("Usage: zstat status [pool]", file=sys.stderr)  # noqa: T201
        sys.exit(1)
