"""
Level 1 Unit Tests: Sync Command CLI Parsing.

Tests for the sync command that auto-detects direction between push and pull.

Test Levels:
- Level 1 (Unit): All tests in this file - pure Python, no external deps
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


# =============================================================================
# Part 1: Pull-specific CLI Options
# =============================================================================


class TestPullCLIOptions:
    """Pull-specific options parsed."""

    def test_keep_pre_snapshot_option_parsed(self) -> None:
        """--keep-pre-snapshot option parsed."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["sync", "testremote:source", "testpool/target", "--keep-pre-snapshot"])

        assert args.keep_pre_snapshot is True

    def test_no_pre_snapshot_option_parsed(self) -> None:
        """--no-pre-snapshot option parsed."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["sync", "testremote:source", "testpool/target", "--no-pre-snapshot"])

        assert args.no_pre_snapshot is True

    def test_default_pre_snapshot_options(self) -> None:
        """Pre-snapshot options default to False."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["sync", "testremote:source", "testpool/target"])

        assert args.keep_pre_snapshot is False
        assert args.no_pre_snapshot is False


# =============================================================================
# Part 2: Sync Command Parsing
# =============================================================================


class TestSyncCommandParsing:
    """CLI accepts source and destination arguments."""

    def test_sync_command_exists(self) -> None:
        """sync command is available."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["sync", "source", "dest"])

        assert args.command == "sync"

    def test_sync_parses_source_and_destination(self) -> None:
        """sync command parses source and destination."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["sync", "testremote:source", "testpool/target"])

        assert args.source == "testremote:source"
        assert args.destination == "testpool/target"

    def test_sync_with_all_options(self) -> None:
        """sync command with all options."""
        from cloud_mirror.cli import parse_args

        args = parse_args([
            "sync",
            "testremote:source",
            "testpool/target",
            "--transfers", "32",
            "--tpslimit", "8",
            "--dry-run",
            "-v",
        ])

        assert args.source == "testremote:source"
        assert args.destination == "testpool/target"
        assert args.transfers == 32
        assert args.tpslimit == 8
        assert args.dry_run is True
        assert args.verbose == 1


# =============================================================================
# Part 3: Direction Detection Integration
# =============================================================================


class TestDirectionDispatch:
    """Main dispatches by detected direction."""

    def test_detect_pull_direction(self) -> None:
        """Remote first -> PULL direction."""
        from cloud_mirror.direction import SyncDirection, detect_direction

        result = detect_direction("testremote:source", "testpool/target")

        assert result.direction == SyncDirection.PULL

    def test_detect_push_direction(self) -> None:
        """Dataset first -> PUSH direction."""
        from cloud_mirror.direction import SyncDirection, detect_direction

        result = detect_direction("testpool/source", "testremote:target")

        assert result.direction == SyncDirection.PUSH


# =============================================================================
# Part 4: Main Entry Point
# =============================================================================


class TestMainEntryPoint:
    """Test main() function."""

    def test_main_function_exists(self) -> None:
        """main() function exists."""
        from cloud_mirror.main import main

        assert main is not None

    def test_run_sync_function_exists(self) -> None:
        """run_sync() function exists for dispatch."""
        from cloud_mirror.main import run_sync

        assert run_sync is not None


# =============================================================================
# Part 5: Exit Codes
# =============================================================================


class TestExitCodes:
    """Exit codes consistent with push."""

    def test_run_pull_returns_int(self) -> None:
        """run_pull returns integer exit code."""
        from cloud_mirror.pull import run_pull

        result = run_pull(
            remote="nonexistent:remote",
            dataset="nonexistent/dataset",
            config_path=Path("/nonexistent/config"),
            verbose=0,
        )

        assert isinstance(result, int)
