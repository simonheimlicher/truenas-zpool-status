"""
Tests for Pull Sync Operations.

Tests for:
- Pre-pull snapshot creation/destruction
- rclone pull command building
- Pull workflow orchestration

Test Levels:
- Level 1 (Unit): Pure functions, command building
- Level 2 (VM): Real ZFS snapshot operations
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    pass


# =============================================================================
# Part 0: Fake Implementation for Unit Testing
# =============================================================================


@dataclass
class OperationCall:
    """Record of an operation call for verification."""

    name: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any] = field(default_factory=dict)


class FakePullOperations:
    """Fake implementation of PullOperations for testing.

    Records all calls in order for verification.
    Can be configured to fail at specific steps.
    """

    def __init__(self) -> None:
        self.calls: list[OperationCall] = []
        self.fail_at: str | None = None
        self.fail_exception: Exception | None = None
        self._mountpoint = Path("/testpool/target")

    def validate_dataset(self, dataset: str) -> Path:
        """Validate dataset and return mountpoint."""
        self.calls.append(OperationCall("validate_dataset", (dataset,)))
        if self.fail_at == "validate_dataset":
            raise self.fail_exception or ValueError("Dataset not found")
        return self._mountpoint

    def validate_remote(self, remote: str, config_path: Path) -> None:
        """Validate rclone remote configuration."""
        self.calls.append(OperationCall("validate_remote", (remote, config_path)))
        if self.fail_at == "validate_remote":
            raise self.fail_exception or ValueError("Remote not configured")

    def create_pre_pull_snapshot(self, dataset: str, timestamp: str) -> str:
        """Create pre-pull snapshot."""
        self.calls.append(OperationCall("create_pre_pull_snapshot", (dataset, timestamp)))
        if self.fail_at == "create_pre_pull_snapshot":
            raise self.fail_exception or ValueError("Snapshot creation failed")
        return f"{dataset}@dropboxpull-pre-{timestamp}"

    def run_rclone_pull(
        self,
        remote: str,
        mountpoint: Path,
        config_path: Path,
        transfers: int,
        tpslimit: int,
        dry_run: bool,
    ) -> int:
        """Run rclone pull."""
        self.calls.append(
            OperationCall(
                "run_rclone_pull",
                (remote, mountpoint, config_path),
                {"transfers": transfers, "tpslimit": tpslimit, "dry_run": dry_run},
            )
        )
        if self.fail_at == "run_rclone_pull":
            raise self.fail_exception or ValueError("Sync failed")
        return 10  # files transferred

    def destroy_snapshot(self, snapshot_name: str) -> None:
        """Destroy snapshot."""
        self.calls.append(OperationCall("destroy_snapshot", (snapshot_name,)))
        if self.fail_at == "destroy_snapshot":
            raise self.fail_exception or ValueError("Destroy failed")


# =============================================================================
# Part 1: Unit Tests - Pre-pull Snapshot Naming
# =============================================================================


class TestPrePullSnapshotNaming:
    """FI1: Pre-pull snapshot naming."""

    def test_snapshot_name_format(self) -> None:
        """Pre-pull snapshot has correct format."""
        from cloud_mirror.pull import get_pre_pull_snapshot_name

        name = get_pre_pull_snapshot_name("testpool/target", "2026-01-03T12-00-00Z")

        assert name == "testpool/target@dropboxpull-pre-2026-01-03T12-00-00Z"

    def test_snapshot_name_prefix(self) -> None:
        """Pre-pull snapshot has dropboxpull-pre prefix."""
        from cloud_mirror.pull import PRE_PULL_SNAPSHOT_PREFIX

        assert PRE_PULL_SNAPSHOT_PREFIX == "dropboxpull-pre"


# =============================================================================
# Part 2: Unit Tests - Pull Command Building
# =============================================================================


class TestPullCommandBuilding:
    """FI2: rclone pull command building."""

    def test_build_pull_command_basic(self) -> None:
        """Build basic pull command."""
        from cloud_mirror.pull import build_pull_command

        cmd = build_pull_command(
            remote="testremote:source",
            mountpoint=Path("/testpool/target"),
            config_path=Path("/etc/rclone.conf"),
            transfers=64,
            tpslimit=12,
            dry_run=False,
        )

        assert "sync" in cmd
        assert "testremote:source" in cmd
        assert "/testpool/target" in cmd
        assert "--config" in cmd
        assert "--links" in cmd  # FI2: restore symlinks
        assert '--exclude=".versions/**"' in cmd or "--exclude" in cmd  # FI2: skip versions

    def test_build_pull_command_dry_run(self) -> None:
        """Build pull command with --dry-run."""
        from cloud_mirror.pull import build_pull_command

        cmd = build_pull_command(
            remote="testremote:source",
            mountpoint=Path("/testpool/target"),
            config_path=Path("/etc/rclone.conf"),
            transfers=64,
            tpslimit=12,
            dry_run=True,
        )

        assert "--dry-run" in cmd


# =============================================================================
# Part 3: Unit Tests - Pull Workflow Orchestration
# =============================================================================


class TestPullWorkflowOrder:
    """FI3: Pull workflow executes in order."""

    def test_workflow_executes_all_steps(self) -> None:
        """FI3: All steps execute in correct order."""
        from cloud_mirror.pull import PullConfig, PullOrchestrator

        ops = FakePullOperations()
        orchestrator = PullOrchestrator(ops)
        config = PullConfig(
            remote="testremote:source",
            dataset="testpool/target",
            config_path=Path("/etc/rclone.conf"),
        )

        result = orchestrator.run(config)

        assert result.success
        call_names = [c.name for c in ops.calls]
        expected_order = [
            "validate_dataset",
            "validate_remote",
            "create_pre_pull_snapshot",
            "run_rclone_pull",
            "destroy_snapshot",  # On success
        ]
        assert call_names == expected_order

    def test_snapshot_destroyed_on_success(self) -> None:
        """FI3: Pre-pull snapshot destroyed after successful sync."""
        from cloud_mirror.pull import PullConfig, PullOrchestrator

        ops = FakePullOperations()
        orchestrator = PullOrchestrator(ops)
        config = PullConfig(
            remote="testremote:source",
            dataset="testpool/target",
            config_path=Path("/etc/rclone.conf"),
        )

        orchestrator.run(config)

        call_names = [c.name for c in ops.calls]
        assert "destroy_snapshot" in call_names


class TestPullWorkflowFailure:
    """FI4: Pre-pull snapshot preserved on failure."""

    def test_snapshot_preserved_on_sync_failure(self) -> None:
        """FI4: Snapshot NOT destroyed when sync fails."""
        from cloud_mirror.pull import PullConfig, PullOrchestrator, SyncError

        ops = FakePullOperations()
        ops.fail_at = "run_rclone_pull"
        ops.fail_exception = SyncError("Sync failed")
        orchestrator = PullOrchestrator(ops)
        config = PullConfig(
            remote="testremote:source",
            dataset="testpool/target",
            config_path=Path("/etc/rclone.conf"),
        )

        with pytest.raises(SyncError):
            orchestrator.run(config)

        call_names = [c.name for c in ops.calls]
        # Snapshot created but NOT destroyed
        assert "create_pre_pull_snapshot" in call_names
        assert "destroy_snapshot" not in call_names

    def test_result_includes_rollback_info_on_failure(self) -> None:
        """FI4: Result includes rollback command on failure."""
        from cloud_mirror.pull import PullConfig, PullOrchestrator, SyncError

        ops = FakePullOperations()
        ops.fail_at = "run_rclone_pull"
        ops.fail_exception = SyncError("Sync failed")
        orchestrator = PullOrchestrator(ops)
        config = PullConfig(
            remote="testremote:source",
            dataset="testpool/target",
            config_path=Path("/etc/rclone.conf"),
        )

        try:
            orchestrator.run(config)
        except SyncError as e:
            # Error should include rollback info
            assert "rollback" in str(e).lower() or hasattr(e, "snapshot_name")


class TestPullWorkflowOptions:
    """FI5, FI6: Keep/skip pre-pull snapshot options."""

    def test_keep_pre_snapshot_preserves_snapshot(self) -> None:
        """FI5: With keep_pre_snapshot=True, snapshot NOT destroyed."""
        from cloud_mirror.pull import PullConfig, PullOrchestrator

        ops = FakePullOperations()
        orchestrator = PullOrchestrator(ops)
        config = PullConfig(
            remote="testremote:source",
            dataset="testpool/target",
            config_path=Path("/etc/rclone.conf"),
            keep_pre_snapshot=True,
        )

        result = orchestrator.run(config)

        assert result.success
        call_names = [c.name for c in ops.calls]
        assert "create_pre_pull_snapshot" in call_names
        assert "destroy_snapshot" not in call_names

    def test_no_pre_snapshot_skips_snapshot(self) -> None:
        """FI6: With no_pre_snapshot=True, snapshot NOT created."""
        from cloud_mirror.pull import PullConfig, PullOrchestrator

        ops = FakePullOperations()
        orchestrator = PullOrchestrator(ops)
        config = PullConfig(
            remote="testremote:source",
            dataset="testpool/target",
            config_path=Path("/etc/rclone.conf"),
            no_pre_snapshot=True,
        )

        result = orchestrator.run(config)

        assert result.success
        call_names = [c.name for c in ops.calls]
        assert "create_pre_pull_snapshot" not in call_names


# =============================================================================
# Part 4: Data Structures
# =============================================================================


class TestPullConfig:
    """Test PullConfig dataclass."""

    def test_has_required_fields(self) -> None:
        """PullConfig has all required fields."""
        from cloud_mirror.pull import PullConfig

        config = PullConfig(
            remote="testremote:source",
            dataset="testpool/target",
            config_path=Path("/etc/rclone.conf"),
        )

        assert config.remote == "testremote:source"
        assert config.dataset == "testpool/target"
        assert config.config_path == Path("/etc/rclone.conf")

    def test_has_optional_fields_with_defaults(self) -> None:
        """PullConfig has optional fields with defaults."""
        from cloud_mirror.pull import PullConfig

        config = PullConfig(
            remote="testremote:source",
            dataset="testpool/target",
            config_path=Path("/etc/rclone.conf"),
        )

        assert config.transfers == 64
        assert config.tpslimit == 12
        assert config.dry_run is False
        assert config.keep_pre_snapshot is False
        assert config.no_pre_snapshot is False


class TestPullResult:
    """Test PullResult dataclass."""

    def test_has_required_fields(self) -> None:
        """PullResult has all required fields."""
        from cloud_mirror.pull import PullResult

        result = PullResult(
            success=True,
            files_transferred=10,
            snapshot_name="testpool/target@dropboxpull-pre-timestamp",
        )

        assert result.success is True
        assert result.files_transferred == 10
        assert result.snapshot_name == "testpool/target@dropboxpull-pre-timestamp"
