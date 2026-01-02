"""
Level 1 Unit Tests: Push Orchestrator.

Tests for cloud_mirror.push module - orchestration logic with dependency injection.

Test Levels:
- Level 1 (Unit): All tests in this file - uses fake PushOperations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from cloud_mirror.push import PushOperations


# =============================================================================
# Part 0: Fake Implementation for Testing
# =============================================================================


@dataclass
class OperationCall:
    """Record of an operation call for verification."""

    name: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any] = field(default_factory=dict)


class FakePushOperations:
    """Fake implementation of PushOperations for testing.

    Records all calls in order for verification.
    Can be configured to fail at specific steps.
    """

    def __init__(self) -> None:
        self.calls: list[OperationCall] = []
        self.fail_at: str | None = None
        self.fail_exception: Exception | None = None
        self._datasets = ["testpool/data", "testpool/data/child"]
        self._clone_path = Path("/testpool/data.cloudmirror")

    def validate_dataset(self, dataset: str) -> None:
        """Validate dataset exists."""
        self.calls.append(OperationCall("validate_dataset", (dataset,)))
        if self.fail_at == "validate_dataset":
            raise self.fail_exception or ValueError("Dataset not found")

    def validate_remote(self, remote: str, config_path: Path) -> None:
        """Validate rclone remote configuration."""
        self.calls.append(OperationCall("validate_remote", (remote, config_path)))
        if self.fail_at == "validate_remote":
            raise self.fail_exception or ValueError("Remote not configured")

    def list_datasets(self, root_dataset: str) -> list[str]:
        """List datasets recursively."""
        self.calls.append(OperationCall("list_datasets", (root_dataset,)))
        if self.fail_at == "list_datasets":
            raise self.fail_exception or ValueError("Failed to list datasets")
        return self._datasets

    def create_snapshot(self, root_dataset: str, snapshot_name: str) -> None:
        """Create recursive snapshot."""
        self.calls.append(OperationCall("create_snapshot", (root_dataset, snapshot_name)))
        if self.fail_at == "create_snapshot":
            raise self.fail_exception or ValueError("Snapshot creation failed")

    def create_clone_tree(
        self,
        root_dataset: str,
        datasets: list[str],
        snapshot_name: str,
    ) -> Path:
        """Create clone tree from snapshot."""
        self.calls.append(
            OperationCall("create_clone_tree", (root_dataset, datasets, snapshot_name))
        )
        if self.fail_at == "create_clone_tree":
            raise self.fail_exception or ValueError("Clone creation failed")
        return self._clone_path

    def sync(
        self,
        source: Path,
        destination: str,
        config_path: Path,
        transfers: int,
        tpslimit: int,
        dry_run: bool,
        keep_versions: int,
        timestamp: str,
    ) -> int:
        """Run rclone sync and return files transferred."""
        self.calls.append(
            OperationCall(
                "sync",
                (source, destination, config_path),
                {
                    "transfers": transfers,
                    "tpslimit": tpslimit,
                    "dry_run": dry_run,
                    "keep_versions": keep_versions,
                    "timestamp": timestamp,
                },
            )
        )
        if self.fail_at == "sync":
            raise self.fail_exception or ValueError("Sync failed")
        return 10  # files transferred

    def cleanup_versions(
        self,
        destination: str,
        config_path: Path,
        keep_versions: int,
    ) -> int:
        """Cleanup old versions and return deleted count."""
        self.calls.append(
            OperationCall(
                "cleanup_versions",
                (destination, config_path, keep_versions),
            )
        )
        if self.fail_at == "cleanup_versions":
            raise self.fail_exception or ValueError("Cleanup failed")
        return 2  # versions deleted

    def destroy_clone_tree(self, root_dataset: str) -> None:
        """Destroy clone tree."""
        self.calls.append(OperationCall("destroy_clone_tree", (root_dataset,)))
        if self.fail_at == "destroy_clone_tree":
            raise self.fail_exception or ValueError("Clone destruction failed")

    def destroy_snapshot(self, root_dataset: str, snapshot_name: str) -> None:
        """Destroy recursive snapshot."""
        self.calls.append(OperationCall("destroy_snapshot", (root_dataset, snapshot_name)))
        if self.fail_at == "destroy_snapshot":
            raise self.fail_exception or ValueError("Snapshot destruction failed")


# =============================================================================
# Part 1: Named Typical Cases - FR1 (Workflow Order)
# =============================================================================


class TestWorkflowOrder:
    """FR1: GIVEN valid dataset and remote WHEN run_push called THEN workflow executes in order."""

    def test_workflow_executes_all_steps_in_order(self) -> None:
        """FR1: All 9 steps execute in correct order."""
        from cloud_mirror.push import PushConfig, PushOrchestrator

        ops = FakePushOperations()
        orchestrator = PushOrchestrator(ops)
        config = PushConfig(
            dataset="testpool/data",
            destination="dropbox:backup",
            config_path=Path("/etc/rclone.conf"),
        )

        result = orchestrator.run(config)

        assert result.success
        call_names = [c.name for c in ops.calls]
        expected_order = [
            "validate_dataset",
            "validate_remote",
            "list_datasets",
            "create_snapshot",
            "create_clone_tree",
            "sync",
            # cleanup_versions only if keep_versions > 0
            "destroy_clone_tree",
            "destroy_snapshot",
        ]
        assert call_names == expected_order

    def test_workflow_includes_cleanup_versions_when_enabled(self) -> None:
        """FR1: Cleanup versions step included when keep_versions > 0."""
        from cloud_mirror.push import PushConfig, PushOrchestrator

        ops = FakePushOperations()
        orchestrator = PushOrchestrator(ops)
        config = PushConfig(
            dataset="testpool/data",
            destination="dropbox:backup",
            config_path=Path("/etc/rclone.conf"),
            keep_versions=3,
        )

        result = orchestrator.run(config)

        assert result.success
        call_names = [c.name for c in ops.calls]
        assert "cleanup_versions" in call_names
        # Verify order: sync before cleanup_versions
        sync_idx = call_names.index("sync")
        cleanup_idx = call_names.index("cleanup_versions")
        assert sync_idx < cleanup_idx

    def test_validate_dataset_receives_correct_dataset(self) -> None:
        """FR1: Step 1 validates the correct dataset."""
        from cloud_mirror.push import PushConfig, PushOrchestrator

        ops = FakePushOperations()
        orchestrator = PushOrchestrator(ops)
        config = PushConfig(
            dataset="tank/photos",
            destination="dropbox:backup",
            config_path=Path("/etc/rclone.conf"),
        )

        orchestrator.run(config)

        validate_call = ops.calls[0]
        assert validate_call.name == "validate_dataset"
        assert validate_call.args == ("tank/photos",)

    def test_validate_remote_receives_correct_args(self) -> None:
        """FR1: Step 2 validates remote with config path."""
        from cloud_mirror.push import PushConfig, PushOrchestrator

        ops = FakePushOperations()
        orchestrator = PushOrchestrator(ops)
        config = PushConfig(
            dataset="testpool/data",
            destination="myremote:backup",
            config_path=Path("/custom/rclone.conf"),
        )

        orchestrator.run(config)

        validate_call = ops.calls[1]
        assert validate_call.name == "validate_remote"
        assert validate_call.args == ("myremote:backup", Path("/custom/rclone.conf"))

    def test_sync_receives_all_config_options(self) -> None:
        """FR1: Sync step receives all configuration options."""
        from cloud_mirror.push import PushConfig, PushOrchestrator

        ops = FakePushOperations()
        orchestrator = PushOrchestrator(ops)
        config = PushConfig(
            dataset="testpool/data",
            destination="dropbox:backup",
            config_path=Path("/etc/rclone.conf"),
            transfers=32,
            tpslimit=8,
            dry_run=True,
            keep_versions=5,
        )

        orchestrator.run(config)

        sync_call = next(c for c in ops.calls if c.name == "sync")
        assert sync_call.kwargs["transfers"] == 32
        assert sync_call.kwargs["tpslimit"] == 8
        assert sync_call.kwargs["dry_run"] is True
        assert sync_call.kwargs["keep_versions"] == 5


# =============================================================================
# Part 2: Named Edge Cases - FR2 (Cleanup on Failure)
# =============================================================================


class TestCleanupOnFailure:
    """FR2: GIVEN push operation fails THEN cleanup still occurs."""

    def test_sync_failure_triggers_cleanup(self) -> None:
        """FR2: When sync fails, clone and snapshot are destroyed."""
        from cloud_mirror.push import PushConfig, PushOrchestrator, SyncError

        ops = FakePushOperations()
        ops.fail_at = "sync"
        ops.fail_exception = SyncError("Sync failed")
        orchestrator = PushOrchestrator(ops)
        config = PushConfig(
            dataset="testpool/data",
            destination="dropbox:backup",
            config_path=Path("/etc/rclone.conf"),
        )

        with pytest.raises(SyncError):
            orchestrator.run(config)

        call_names = [c.name for c in ops.calls]
        assert "destroy_clone_tree" in call_names
        assert "destroy_snapshot" in call_names

    def test_sync_failure_reraises_original_error(self) -> None:
        """FR2: Original SyncError is re-raised after cleanup."""
        from cloud_mirror.push import PushConfig, PushOrchestrator, SyncError

        ops = FakePushOperations()
        ops.fail_at = "sync"
        ops.fail_exception = SyncError("Rate limit exceeded")
        orchestrator = PushOrchestrator(ops)
        config = PushConfig(
            dataset="testpool/data",
            destination="dropbox:backup",
            config_path=Path("/etc/rclone.conf"),
        )

        with pytest.raises(SyncError, match="Rate limit exceeded"):
            orchestrator.run(config)

    def test_clone_tree_failure_cleans_up_snapshot(self) -> None:
        """FR2: When clone tree creation fails, snapshot is still destroyed."""
        from cloud_mirror.push import CloneError, PushConfig, PushOrchestrator

        ops = FakePushOperations()
        ops.fail_at = "create_clone_tree"
        ops.fail_exception = CloneError("Clone failed")
        orchestrator = PushOrchestrator(ops)
        config = PushConfig(
            dataset="testpool/data",
            destination="dropbox:backup",
            config_path=Path("/etc/rclone.conf"),
        )

        with pytest.raises(CloneError):
            orchestrator.run(config)

        call_names = [c.name for c in ops.calls]
        # Clone tree was never created, so no destroy_clone_tree
        assert "destroy_clone_tree" not in call_names
        # But snapshot was created, so it should be destroyed
        assert "destroy_snapshot" in call_names

    def test_validation_failure_skips_all_operations(self) -> None:
        """FR2: Validation failure means no resources to clean up."""
        from cloud_mirror.push import PushConfig, PushOrchestrator, ValidationError

        ops = FakePushOperations()
        ops.fail_at = "validate_dataset"
        ops.fail_exception = ValidationError("Dataset not found")
        orchestrator = PushOrchestrator(ops)
        config = PushConfig(
            dataset="testpool/data",
            destination="dropbox:backup",
            config_path=Path("/etc/rclone.conf"),
        )

        with pytest.raises(ValidationError):
            orchestrator.run(config)

        call_names = [c.name for c in ops.calls]
        assert call_names == ["validate_dataset"]
        # No resources created, no cleanup needed


# =============================================================================
# Part 3: Keep Flags - FR3 (Cleanup Skipped)
# =============================================================================


class TestKeepFlags:
    """FR3: GIVEN keep flags set WHEN push completes THEN resources preserved."""

    def test_keep_clone_preserves_clone_tree(self) -> None:
        """FR3: When keep_clone=True, clone tree is not destroyed."""
        from cloud_mirror.push import PushConfig, PushOrchestrator

        ops = FakePushOperations()
        orchestrator = PushOrchestrator(ops)
        config = PushConfig(
            dataset="testpool/data",
            destination="dropbox:backup",
            config_path=Path("/etc/rclone.conf"),
            keep_clone=True,
        )

        result = orchestrator.run(config)

        assert result.success
        call_names = [c.name for c in ops.calls]
        assert "destroy_clone_tree" not in call_names
        # Snapshot still destroyed by default
        assert "destroy_snapshot" in call_names

    def test_keep_snapshot_preserves_snapshot(self) -> None:
        """FR3: When keep_snapshot=True, snapshot is not destroyed."""
        from cloud_mirror.push import PushConfig, PushOrchestrator

        ops = FakePushOperations()
        orchestrator = PushOrchestrator(ops)
        config = PushConfig(
            dataset="testpool/data",
            destination="dropbox:backup",
            config_path=Path("/etc/rclone.conf"),
            keep_snapshot=True,
        )

        result = orchestrator.run(config)

        assert result.success
        call_names = [c.name for c in ops.calls]
        assert "destroy_snapshot" not in call_names
        # Clone still destroyed by default
        assert "destroy_clone_tree" in call_names

    def test_both_keep_flags_preserve_both(self) -> None:
        """FR3: When both keep flags True, neither is destroyed."""
        from cloud_mirror.push import PushConfig, PushOrchestrator

        ops = FakePushOperations()
        orchestrator = PushOrchestrator(ops)
        config = PushConfig(
            dataset="testpool/data",
            destination="dropbox:backup",
            config_path=Path("/etc/rclone.conf"),
            keep_clone=True,
            keep_snapshot=True,
        )

        result = orchestrator.run(config)

        assert result.success
        call_names = [c.name for c in ops.calls]
        assert "destroy_clone_tree" not in call_names
        assert "destroy_snapshot" not in call_names

    def test_keep_flags_respected_on_failure(self) -> None:
        """FR3: Keep flags are respected even when sync fails."""
        from cloud_mirror.push import PushConfig, PushOrchestrator, SyncError

        ops = FakePushOperations()
        ops.fail_at = "sync"
        ops.fail_exception = SyncError("Sync failed")
        orchestrator = PushOrchestrator(ops)
        config = PushConfig(
            dataset="testpool/data",
            destination="dropbox:backup",
            config_path=Path("/etc/rclone.conf"),
            keep_clone=True,
            keep_snapshot=True,
        )

        with pytest.raises(SyncError):
            orchestrator.run(config)

        call_names = [c.name for c in ops.calls]
        assert "destroy_clone_tree" not in call_names
        assert "destroy_snapshot" not in call_names


# =============================================================================
# Part 4: Protocol - FR4 (Dependency Injection)
# =============================================================================


class TestProtocolCompliance:
    """FR4: GIVEN PushOperations protocol THEN any implementation works."""

    def test_accepts_fake_implementation(self) -> None:
        """FR4: Orchestrator accepts FakePushOperations."""
        from cloud_mirror.push import PushConfig, PushOrchestrator

        ops = FakePushOperations()
        orchestrator = PushOrchestrator(ops)
        config = PushConfig(
            dataset="testpool/data",
            destination="dropbox:backup",
            config_path=Path("/etc/rclone.conf"),
        )

        result = orchestrator.run(config)

        assert result.success

    def test_result_contains_files_transferred(self) -> None:
        """FR4: PushResult includes files_transferred from sync."""
        from cloud_mirror.push import PushConfig, PushOrchestrator

        ops = FakePushOperations()
        orchestrator = PushOrchestrator(ops)
        config = PushConfig(
            dataset="testpool/data",
            destination="dropbox:backup",
            config_path=Path("/etc/rclone.conf"),
        )

        result = orchestrator.run(config)

        assert result.files_transferred == 10

    def test_result_contains_clone_path(self) -> None:
        """FR4: PushResult includes clone_path."""
        from cloud_mirror.push import PushConfig, PushOrchestrator

        ops = FakePushOperations()
        orchestrator = PushOrchestrator(ops)
        config = PushConfig(
            dataset="testpool/data",
            destination="dropbox:backup",
            config_path=Path("/etc/rclone.conf"),
            keep_clone=True,  # So we get the path back
        )

        result = orchestrator.run(config)

        assert result.clone_path == Path("/testpool/data.cloudmirror")


# =============================================================================
# Part 5: Systematic Coverage
# =============================================================================


class TestSystematicCoverage:
    """GIVEN all failure points WHEN testing THEN cleanup always occurs."""

    @pytest.mark.parametrize(
        ("fail_point", "expect_destroy_clone", "expect_destroy_snapshot"),
        [
            ("validate_dataset", False, False),  # Nothing created
            ("validate_remote", False, False),  # Nothing created
            ("list_datasets", False, False),  # Nothing created
            ("create_snapshot", False, False),  # Snapshot creation failed
            ("create_clone_tree", False, True),  # Snapshot created, clone failed
            ("sync", True, True),  # Both created, sync failed
            ("cleanup_versions", True, True),  # Cleanup failed but continues
        ],
    )
    def test_cleanup_behavior_at_each_failure_point(
        self,
        fail_point: str,
        expect_destroy_clone: bool,
        expect_destroy_snapshot: bool,
    ) -> None:
        """Verify cleanup behavior when failure occurs at each step."""
        from cloud_mirror.push import PushConfig, PushOrchestrator

        ops = FakePushOperations()
        ops.fail_at = fail_point
        ops.fail_exception = ValueError(f"Failed at {fail_point}")
        orchestrator = PushOrchestrator(ops)
        config = PushConfig(
            dataset="testpool/data",
            destination="dropbox:backup",
            config_path=Path("/etc/rclone.conf"),
            keep_versions=3,  # Enable cleanup_versions step
        )

        try:
            orchestrator.run(config)
        except Exception:  # noqa: S110 - intentionally ignoring to verify cleanup behavior
            pass

        call_names = [c.name for c in ops.calls]

        if expect_destroy_clone:
            assert "destroy_clone_tree" in call_names
        else:
            assert "destroy_clone_tree" not in call_names

        if expect_destroy_snapshot:
            assert "destroy_snapshot" in call_names
        else:
            assert "destroy_snapshot" not in call_names
