"""
Main entry point for cloud-mirror.

This module provides:
- main(): Entry point for the cloud-mirror CLI
- run_sync(): Dispatcher that auto-detects direction and calls run_push or run_pull
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import Namespace


def run_sync(
    source: str,
    destination: str,
    config_path: Path | None = None,
    transfers: int = 64,
    tpslimit: int = 12,
    dry_run: bool = False,
    verbose: int = 0,
    # Push-specific
    keep_versions: int = 0,
    keep_snapshot: bool = False,
    keep_clone: bool = False,
    # Pull-specific
    keep_pre_snapshot: bool = False,
    no_pre_snapshot: bool = False,
) -> int:
    """Execute a sync operation, auto-detecting direction.

    Direction is determined by argument format:
    - source is remote (has :) -> PULL (remote to local)
    - destination is remote (has :) -> PUSH (local to remote)

    Args:
        source: Source path (dataset or remote).
        destination: Destination path (remote or dataset).
        config_path: Path to rclone config file.
        transfers: Number of parallel transfers.
        tpslimit: Transactions per second limit.
        dry_run: If True, perform trial run.
        verbose: Verbosity level.
        keep_versions: Number of old versions to keep (push only).
        keep_snapshot: Keep snapshot after sync (push only).
        keep_clone: Keep clone tree after sync (push only).
        keep_pre_snapshot: Keep pre-pull snapshot after sync (pull only).
        no_pre_snapshot: Skip creating pre-pull snapshot (pull only).

    Returns:
        Exit code: 0 for success, 1 for failure.
    """
    from cloud_mirror.direction import DirectionError, SyncDirection, detect_direction

    try:
        endpoints = detect_direction(source, destination)
    except DirectionError as e:
        print(f"Error: {e}", file=sys.stderr)  # noqa: T201
        return 1

    if endpoints.direction == SyncDirection.PUSH:
        from cloud_mirror.push import run_push

        return run_push(
            dataset=endpoints.zfs_dataset,
            destination=endpoints.remote,
            config_path=config_path,
            transfers=transfers,
            tpslimit=tpslimit,
            dry_run=dry_run,
            keep_versions=keep_versions,
            keep_snapshot=keep_snapshot,
            keep_clone=keep_clone,
            verbose=verbose,
        )
    else:
        from cloud_mirror.pull import run_pull

        return run_pull(
            remote=endpoints.remote,
            dataset=endpoints.zfs_dataset,
            config_path=config_path,
            transfers=transfers,
            tpslimit=tpslimit,
            dry_run=dry_run,
            keep_pre_snapshot=keep_pre_snapshot,
            no_pre_snapshot=no_pre_snapshot,
            verbose=verbose,
        )


def main(args: list[str] | None = None) -> int:
    """Main entry point for cloud-mirror CLI.

    Args:
        args: Command-line arguments (uses sys.argv if None).

    Returns:
        Exit code: 0 for success, non-zero for failure.
    """
    from cloud_mirror.cli import parse_args

    parsed = parse_args(args)

    if parsed.command is None:
        print("Error: No command specified. Use --help for usage.", file=sys.stderr)  # noqa: T201
        return 1

    if parsed.command == "push":
        from cloud_mirror.push import run_push

        return run_push(
            dataset=parsed.dataset,
            destination=parsed.destination,
            config_path=parsed.config,
            transfers=parsed.transfers,
            tpslimit=parsed.tpslimit,
            dry_run=parsed.dry_run,
            keep_versions=parsed.keep_versions,
            keep_snapshot=parsed.keep_snapshot,
            keep_clone=parsed.keep_clone,
            verbose=parsed.verbose,
        )

    elif parsed.command == "sync":
        return run_sync(
            source=parsed.source,
            destination=parsed.destination,
            config_path=parsed.config,
            transfers=parsed.transfers,
            tpslimit=parsed.tpslimit,
            dry_run=parsed.dry_run,
            verbose=parsed.verbose,
            keep_versions=parsed.keep_versions,
            keep_snapshot=parsed.keep_snapshot,
            keep_clone=parsed.keep_clone,
            keep_pre_snapshot=parsed.keep_pre_snapshot,
            no_pre_snapshot=parsed.no_pre_snapshot,
        )

    else:
        print(f"Error: Unknown command '{parsed.command}'", file=sys.stderr)  # noqa: T201
        return 1


if __name__ == "__main__":
    sys.exit(main())
