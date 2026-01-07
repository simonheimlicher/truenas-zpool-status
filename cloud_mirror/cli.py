"""
CLI argument parsing for cloud-mirror.

This module provides argument parsing for the cloud-mirror command-line tool.
It uses argparse with simple positional arguments (no subcommands).
Direction detection happens in main.py based on argument format.

Usage:
    cloud-mirror <source> <destination> [options]
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import Namespace

# Default values for options
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
    """Create the argument parser.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        prog="cloud-mirror",
        description="Mirror ZFS datasets to/from cloud storage with snapshot-based consistency.",
    )

    parser.add_argument(
        "source",
        type=str,
        help="Source (dataset for mirror-to-cloud, remote for mirror-from-cloud)",
    )

    parser.add_argument(
        "destination",
        type=str,
        help="Destination (remote for mirror-to-cloud, dataset for mirror-from-cloud)",
    )

    # Common options
    parser.add_argument(
        "--transfers",
        type=_positive_int,
        default=DEFAULT_TRANSFERS,
        metavar="N",
        help=f"Number of parallel transfers (default: {DEFAULT_TRANSFERS})",
    )

    parser.add_argument(
        "--tpslimit",
        type=_positive_int,
        default=DEFAULT_TPSLIMIT,
        metavar="N",
        help=f"Transactions per second limit (default: {DEFAULT_TPSLIMIT})",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Perform a trial run with no changes made",
    )

    parser.add_argument(
        "--config",
        type=_path_type,
        default=None,
        metavar="PATH",
        help="Path to rclone configuration file",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase output verbosity (use -v, -vv, or -vvv)",
    )

    # Mirror-to-cloud specific options
    parser.add_argument(
        "--keep-versions",
        type=_positive_int,
        default=DEFAULT_KEEP_VERSIONS,
        metavar="N",
        help=f"Number of old versions to keep on remote (default: {DEFAULT_KEEP_VERSIONS})",
    )

    parser.add_argument(
        "--keep-snapshot",
        action="store_true",
        default=False,
        help="Keep snapshot after mirror (default: destroy)",
    )

    parser.add_argument(
        "--keep-clone",
        action="store_true",
        default=False,
        help="Keep clone tree after mirror (default: destroy)",
    )

    # Mirror-from-cloud specific options
    parser.add_argument(
        "--keep-pre-snapshot",
        action="store_true",
        default=False,
        help="Keep pre-mirror snapshot after mirror (default: destroy on success)",
    )

    parser.add_argument(
        "--no-pre-snapshot",
        action="store_true",
        default=False,
        help="Skip creating pre-mirror snapshot (default: create)",
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
    return parser.parse_args(args)
