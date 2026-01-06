"""
Level 1 Unit Tests: run_push function and RealPushOperations.

Tests for CLI integration wiring - CLI argument handling, error messages,
config file defaults, and verbose flag behavior.

Test Levels:
- Level 1 (Unit): All tests in this file - pure Python, no external deps
"""

from __future__ import annotations

from pathlib import Path

import pytest


# =============================================================================
# Part 1: Config File Defaults (FR5)
# =============================================================================


class TestConfigFileDefaults:
    """FR5: Config file option defaults."""

    def test_default_config_path_is_rclone_default(self) -> None:
        """WHEN no --config specified THEN uses ~/.config/rclone/rclone.conf."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["push", "testpool/data", "remote:backup"])

        # config should be None (will be resolved to default later)
        assert args.config is None

    def test_custom_config_path_parsed(self) -> None:
        """WHEN --config specified THEN uses specified path."""
        from cloud_mirror.cli import parse_args

        args = parse_args(
            ["push", "testpool/data", "remote:backup", "--config", "/custom/rclone.conf"]
        )

        assert args.config == Path("/custom/rclone.conf")


# =============================================================================
# Part 2: Error Message Formatting (FR4)
# =============================================================================


class TestErrorMessageFormatting:
    """FR4: User-friendly error messages."""

    def test_validation_error_has_friendly_message(self) -> None:
        """WHEN ValidationError raised THEN message is user-friendly."""
        from cloud_mirror.push import ValidationError

        error = ValidationError("Dataset 'tank/data' does not exist")

        # Error message should be clear
        assert "tank/data" in str(error)
        assert "does not exist" in str(error)

    def test_lock_error_has_friendly_message(self) -> None:
        """WHEN LockError raised THEN message includes resolution suggestion."""
        from cloud_mirror.push import LockError

        error = LockError("testpool", Path("/var/run/cloud-mirror/testpool.lock"))

        msg = str(error)
        assert "testpool" in msg
        assert "another operation" in msg.lower()

    def test_sync_error_has_friendly_message(self) -> None:
        """WHEN SyncError raised THEN message is user-friendly."""
        from cloud_mirror.push import SyncError

        error = SyncError("Sync failed: Rate limit exceeded")

        assert "Rate limit" in str(error)


# =============================================================================
# Part 3: Dry Run Flag (FR2)
# =============================================================================


class TestDryRunFlag:
    """FR2: Dry run mode parsing."""

    def test_dry_run_flag_parsed(self) -> None:
        """WHEN --dry-run specified THEN flag is True."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["push", "testpool/data", "remote:backup", "--dry-run"])

        assert args.dry_run is True

    def test_dry_run_default_is_false(self) -> None:
        """WHEN --dry-run not specified THEN flag is False."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["push", "testpool/data", "remote:backup"])

        assert args.dry_run is False


# =============================================================================
# Part 4: Verbose Flag (FR3)
# =============================================================================


class TestVerboseFlag:
    """FR3: Verbose output levels."""

    def test_single_v_sets_verbose_1(self) -> None:
        """WHEN -v specified THEN verbose is 1."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["push", "testpool/data", "remote:backup", "-v"])

        assert args.verbose == 1

    def test_double_v_sets_verbose_2(self) -> None:
        """WHEN -vv specified THEN verbose is 2."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["push", "testpool/data", "remote:backup", "-vv"])

        assert args.verbose == 2

    def test_no_v_sets_verbose_0(self) -> None:
        """WHEN no -v specified THEN verbose is 0."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["push", "testpool/data", "remote:backup"])

        assert args.verbose == 0


# =============================================================================
# Part 5: RealPushOperations (FR1)
# =============================================================================


class TestRealPushOperationsExists:
    """FR1: RealPushOperations class exists and implements protocol."""

    def test_real_push_operations_importable(self) -> None:
        """WHEN importing RealPushOperations THEN it exists."""
        from cloud_mirror.push import RealPushOperations

        assert RealPushOperations is not None

    def test_real_push_operations_has_required_methods(self) -> None:
        """WHEN creating RealPushOperations THEN has all protocol methods."""
        import logging

        from cloud_mirror.push import RealPushOperations

        # Should be able to instantiate
        ops = RealPushOperations(logging.getLogger("test"))

        # Should have all required methods
        assert hasattr(ops, "validate_dataset")
        assert hasattr(ops, "validate_remote")
        assert hasattr(ops, "list_datasets")
        assert hasattr(ops, "create_snapshot")
        assert hasattr(ops, "create_clone_tree")
        assert hasattr(ops, "sync")
        assert hasattr(ops, "cleanup_versions")
        assert hasattr(ops, "destroy_clone_tree")
        assert hasattr(ops, "destroy_snapshot")


class TestRunPushFunctionExists:
    """FR1: run_push function wires everything together."""

    def test_run_push_function_exists(self) -> None:
        """WHEN importing run_push THEN it exists."""
        from cloud_mirror.push import run_push

        assert run_push is not None

    def test_run_push_function_signature(self) -> None:
        """WHEN calling run_push THEN has expected parameters."""
        import inspect

        from cloud_mirror.push import run_push

        sig = inspect.signature(run_push)
        params = list(sig.parameters.keys())

        # Should have all expected parameters
        assert "dataset" in params
        assert "destination" in params
        assert "config_path" in params
        assert "dry_run" in params
        assert "verbose" in params
