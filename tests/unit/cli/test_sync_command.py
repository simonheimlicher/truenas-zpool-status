"""
Level 1 Unit Tests: Pull-specific CLI Options.

Tests for pull-specific CLI options that are available in the unified interface.

Test Levels:
- Level 1 (Unit): All tests in this file - pure Python, no external deps
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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

        args = parse_args(
            ["testremote:source", "testpool/target", "--keep-pre-snapshot"]
        )

        assert args.keep_pre_snapshot is True

    def test_no_pre_snapshot_option_parsed(self) -> None:
        """--no-pre-snapshot option parsed."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["testremote:source", "testpool/target", "--no-pre-snapshot"])

        assert args.no_pre_snapshot is True

    def test_default_pre_snapshot_options(self) -> None:
        """Pre-snapshot options default to False."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["testremote:source", "testpool/target"])

        assert args.keep_pre_snapshot is False
        assert args.no_pre_snapshot is False


# =============================================================================
# Part 2: Direction Detection in Main
# =============================================================================


class TestDirectionDispatch:
    """Main dispatches based on detected direction."""

    def test_detect_pull_direction(self) -> None:
        """Remote first detects as PULL."""
        from cloud_mirror.direction import SyncDirection, detect_direction

        endpoints = detect_direction("testremote:source", "testpool/target")

        assert endpoints.direction == SyncDirection.PULL
        assert endpoints.remote == "testremote:source"
        assert endpoints.zfs_dataset == "testpool/target"

    def test_detect_push_direction(self) -> None:
        """Dataset first detects as PUSH."""
        from cloud_mirror.direction import SyncDirection, detect_direction

        endpoints = detect_direction("testpool/source", "testremote:dest")

        assert endpoints.direction == SyncDirection.PUSH
        assert endpoints.zfs_dataset == "testpool/source"
        assert endpoints.remote == "testremote:dest"


# =============================================================================
# Part 3: Main Entry Point
# =============================================================================


class TestMainEntryPoint:
    """Main function exists and dispatches."""

    def test_main_function_exists(self) -> None:
        """main() function exists."""
        from cloud_mirror.main import main

        assert callable(main)


# =============================================================================
# Part 4: Exit Codes
# =============================================================================


class TestExitCodes:
    """Functions return appropriate exit codes."""

    def test_run_pull_returns_int(self) -> None:
        """run_pull returns int exit code."""
        from cloud_mirror.pull import run_pull

        # Verify signature returns int (using callable inspection)
        # Note: With PEP 563, annotations are strings
        assert run_pull.__annotations__.get("return") == "int"
