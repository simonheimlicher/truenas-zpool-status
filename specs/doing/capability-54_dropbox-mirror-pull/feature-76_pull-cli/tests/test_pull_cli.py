"""
Tests for Pull CLI Integration.

Tests for:
- CLI parsing for pull-specific options
- Direction-based dispatch (push vs pull)
- Main entry point

Test Levels:
- Level 1 (Unit): CLI parsing, direction dispatch logic
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture


# =============================================================================
# Part 1: Pull-specific CLI Options (FI2)
# =============================================================================


class TestPullCLIOptions:
    """FI2: Pull-specific options parsed."""

    def test_keep_pre_snapshot_option_parsed(self) -> None:
        """--keep-pre-snapshot option parsed."""
        from cloud_mirror.cli import parse_args

        # Using 'sync' command with pull-like args
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
# Part 2: Sync Command Parsing (FI1)
# =============================================================================


class TestSyncCommandParsing:
    """FI1: CLI accepts source and destination arguments."""

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
# Part 3: Direction Detection Integration (FI3)
# =============================================================================


class TestDirectionDispatch:
    """FI3: Main dispatches by detected direction."""

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
# Part 4: Dry Run (FI5)
# =============================================================================


class TestDryRunPull:
    """FI5: Dry run works for pull."""

    def test_dry_run_option_available(self) -> None:
        """--dry-run option available for sync."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["sync", "testremote:source", "testpool/target", "--dry-run"])

        assert args.dry_run is True


# =============================================================================
# Part 5: Exit Codes (FI6)
# =============================================================================


class TestExitCodes:
    """FI6: Exit codes consistent with push."""

    def test_run_pull_returns_int(self) -> None:
        """run_pull returns integer exit code."""
        from cloud_mirror.pull import run_pull

        # This will fail validation but should return an int
        result = run_pull(
            remote="nonexistent:remote",
            dataset="nonexistent/dataset",
            config_path=Path("/nonexistent/config"),
            verbose=0,
        )

        assert isinstance(result, int)


# =============================================================================
# Part 6: Main Entry Point
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
