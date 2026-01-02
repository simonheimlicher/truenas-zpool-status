"""
CLI argument parsing for cloud-mirror.

This module provides argument parsing for the cloud-mirror command-line tool.
It uses argparse with subcommands (push, pull - future).

Usage:
    cloud-mirror.py push <dataset> <destination> [options]
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import Namespace

# Default values for push options
DEFAULT_TRANSFERS = 64
DEFAULT_TPSLIMIT = 12
DEFAULT_KEEP_VERSIONS = 0


def _positive_int(value: str) -> int:
    """Validate that value is a non-negative integer.

    Args:
        value: String value to parse.

    Returns:
        Parsed integer.

    Raises:
        argparse.ArgumentTypeError: If value is not a non-negative integer.
    """
    try:
        ivalue = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"invalid int value: '{value}'") from e

    if ivalue < 0:
        raise argparse.ArgumentTypeError(f"must be non-negative: {value}")

    return ivalue


def _path_type(value: str) -> Path:
    """Convert string to Path.

    Args:
        value: String path value.

    Returns:
        Path object.
    """
    return Path(value)


def _create_parser() -> argparse.ArgumentParser:
    """Create the argument parser with all subcommands.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        prog="cloud-mirror",
        description="Sync ZFS datasets to cloud storage with snapshot-based consistency.",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase output verbosity (use -v, -vv, or -vvv)",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        description="Available commands",
    )

    # Push subcommand
    push_parser = subparsers.add_parser(
        "push",
        help="Push local ZFS dataset to remote",
        description="Push a ZFS dataset to a remote destination using rclone.",
    )

    push_parser.add_argument(
        "dataset",
        type=str,
        help="ZFS dataset to push (e.g., pool/data)",
    )

    push_parser.add_argument(
        "destination",
        type=str,
        help="Remote destination (e.g., dropbox:backup)",
    )

    push_parser.add_argument(
        "--keep-versions",
        type=_positive_int,
        default=DEFAULT_KEEP_VERSIONS,
        metavar="N",
        help=f"Number of old versions to keep (default: {DEFAULT_KEEP_VERSIONS})",
    )

    push_parser.add_argument(
        "--keep-snapshot",
        action="store_true",
        default=False,
        help="Keep snapshot after sync (default: destroy)",
    )

    push_parser.add_argument(
        "--keep-clone",
        action="store_true",
        default=False,
        help="Keep clone tree after sync (default: destroy)",
    )

    push_parser.add_argument(
        "--transfers",
        type=_positive_int,
        default=DEFAULT_TRANSFERS,
        metavar="N",
        help=f"Number of parallel transfers (default: {DEFAULT_TRANSFERS})",
    )

    push_parser.add_argument(
        "--tpslimit",
        type=_positive_int,
        default=DEFAULT_TPSLIMIT,
        metavar="N",
        help=f"Transactions per second limit (default: {DEFAULT_TPSLIMIT})",
    )

    push_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Perform a trial run with no changes made",
    )

    push_parser.add_argument(
        "--config",
        type=_path_type,
        default=None,
        metavar="PATH",
        help="Path to rclone configuration file",
    )

    # Add verbose flag to push subcommand as well
    push_parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase output verbosity (use -v, -vv, or -vvv)",
    )

    return parser


def parse_args(args: list[str] | None = None) -> Namespace:
    """Parse command-line arguments.

    Args:
        args: List of arguments to parse. If None, uses sys.argv[1:].

    Returns:
        Parsed arguments as Namespace.

    Raises:
        SystemExit: If arguments are invalid or --help is requested.
    """
    parser = _create_parser()
    parsed = parser.parse_args(args)

    # Merge verbose from main parser and subparser
    # The subparser's -v flag is preferred if both are used
    if hasattr(parsed, "verbose") and parsed.verbose is None:
        parsed.verbose = 0

    return parsed
