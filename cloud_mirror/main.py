"""
Main entry point for cloud-mirror.

This module provides:
- main(): Entry point for the cloud-mirror CLI with auto-direction detection
"""

from __future__ import annotations

import sys


def main(args: list[str] | None = None) -> int:
    """Main entry point for cloud-mirror CLI.

    Auto-detects direction (mirror-to-cloud or mirror-from-cloud) based on
    argument format and dispatches to appropriate handler.

    Args:
        args: Command-line arguments (uses sys.argv if None).

    Returns:
        Exit code: 0 for success, non-zero for failure.
    """
    from cloud_mirror.cli import parse_args
    from cloud_mirror.direction import DirectionError, SyncDirection, detect_direction

    parsed = parse_args(args)

    # Auto-detect direction from source and destination
    try:
        endpoints = detect_direction(parsed.source, parsed.destination)
    except DirectionError as e:
        print(f"Error: {e}", file=sys.stderr)  # noqa: T201
        return 1

    if endpoints.direction == SyncDirection.PUSH:
        from cloud_mirror.push import run_push

        return run_push(
            dataset=endpoints.zfs_dataset,
            destination=endpoints.remote,
            config_path=parsed.config,
            transfers=parsed.transfers,
            tpslimit=parsed.tpslimit,
            dry_run=parsed.dry_run,
            keep_versions=parsed.keep_versions,
            keep_snapshot=parsed.keep_snapshot,
            keep_clone=parsed.keep_clone,
            verbose=parsed.verbose,
        )
    else:
        from cloud_mirror.pull import run_pull

        return run_pull(
            remote=endpoints.remote,
            dataset=endpoints.zfs_dataset,
            config_path=parsed.config,
            transfers=parsed.transfers,
            tpslimit=parsed.tpslimit,
            dry_run=parsed.dry_run,
            keep_pre_snapshot=parsed.keep_pre_snapshot,
            no_pre_snapshot=parsed.no_pre_snapshot,
            verbose=parsed.verbose,
        )


if __name__ == "__main__":
    sys.exit(main())
