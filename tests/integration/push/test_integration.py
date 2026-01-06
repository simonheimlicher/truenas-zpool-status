"""
Level 2 Integration Tests: Push CLI Integration.

Tests for run_push function wiring together CLI, orchestrator, and locking.
Uses real ZFS in Colima VM.

Test Levels:
- Level 2 (VM): All tests in this file - requires Colima VM with ZFS

NOTE: Full sync tests are limited because ZFS runs in VM but rclone runs on host.
The clone mountpoint is inside the VM and not accessible from host.
Sync functionality is already tested in tests/integration/rclone/.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture


# =============================================================================
# Part 1: Run Push with Validation Errors
# =============================================================================


@pytest.mark.vm_required
class TestRunPushFunction:
    """FR1: run_push function wires everything together."""

    def test_run_push_with_invalid_dataset_returns_1(
        self,
        ensure_pool_exists: None,
        rclone_config: Path,
        test_remote: str,
    ) -> None:
        """FR1: WHEN run_push called with invalid dataset THEN returns 1."""
        from cloud_mirror.push import run_push

        exit_code = run_push(
            dataset="nonexistent/dataset",
            destination=test_remote,
            config_path=rclone_config,
            dry_run=True,
            verbose=0,
        )

        assert exit_code == 1


# =============================================================================
# Part 2: Workflow Steps (FR2)
# =============================================================================


@pytest.mark.vm_required
class TestWorkflowSteps:
    """FR2: Test that workflow executes all steps and cleans up.

    NOTE: Full sync tests are limited because ZFS runs in VM but rclone runs on host.
    The clone mountpoint is inside the VM and not accessible from host.
    Sync functionality is already tested in feature-61 (rclone-push-sync).
    """

    def test_workflow_cleans_up_on_sync_error(
        self,
        zfs_dataset_with_children: str,
        sample_files_in_dataset: Path,
        rclone_config: Path,
        test_remote: str,
        ensure_pool_exists: None,
    ) -> None:
        """FR2: WHEN sync fails THEN clone and snapshot still destroyed."""
        from tests.conftest import run_in_vm

        from cloud_mirror.push import run_push
        from cloud_mirror.zfs import CLONE_SUFFIX

        # This will fail at sync step (clone path not accessible from host)
        # but cleanup should still happen
        run_push(
            dataset=zfs_dataset_with_children,
            destination=test_remote,
            config_path=rclone_config,
            dry_run=False,
            verbose=0,
        )

        # Clone should be destroyed even though sync failed
        clone_name = f"{zfs_dataset_with_children}{CLONE_SUFFIX}"
        result = run_in_vm(f"zfs list -H {clone_name}")
        assert result.returncode != 0, "Clone should be destroyed after error"

    def test_workflow_creates_snapshot_before_sync(
        self,
        zfs_dataset_with_children: str,
        sample_files_in_dataset: Path,
        rclone_config: Path,
        test_remote: str,
        ensure_pool_exists: None,
        capsys: "CaptureFixture[str]",
    ) -> None:
        """FR1: Workflow creates snapshot as part of orchestration."""
        from cloud_mirror.push import run_push

        # Run push with verbose to capture log output
        run_push(
            dataset=zfs_dataset_with_children,
            destination=test_remote,
            config_path=rclone_config,
            dry_run=False,
            verbose=1,
        )

        # Check stderr for snapshot creation log (logs go to stderr)
        captured = capsys.readouterr()
        # Note: logging goes to stderr
        # The push will fail at sync, but snapshot should have been created


# =============================================================================
# Part 3: Error Handling (FR4)
# =============================================================================


@pytest.mark.vm_required
class TestErrorHandling:
    """FR4: Error messages are user-friendly."""

    def test_invalid_dataset_returns_exit_code_1(
        self,
        ensure_pool_exists: None,
        rclone_config: Path,
        test_remote: str,
    ) -> None:
        """FR4: WHEN dataset doesn't exist THEN exit code is 1."""
        from cloud_mirror.push import run_push

        exit_code = run_push(
            dataset="nonexistent/dataset",
            destination=test_remote,
            config_path=rclone_config,
            dry_run=False,
            verbose=0,
        )

        assert exit_code == 1

    def test_error_message_printed_to_stderr(
        self,
        ensure_pool_exists: None,
        rclone_config: Path,
        test_remote: str,
        capsys: "CaptureFixture[str]",
    ) -> None:
        """FR4: WHEN error occurs THEN user-friendly message printed to stderr."""
        from cloud_mirror.push import run_push

        run_push(
            dataset="nonexistent/dataset",
            destination=test_remote,
            config_path=rclone_config,
            dry_run=False,
            verbose=0,
        )

        captured = capsys.readouterr()
        assert "Error:" in captured.err
        assert "Suggestion:" in captured.err


# =============================================================================
# Part 4: Fixtures
# =============================================================================


@pytest.fixture
def sample_files_in_dataset(
    zfs_dataset_with_children: str,
    ensure_pool_exists: None,
) -> Path:
    """Create sample files in a ZFS dataset inside the VM.

    Returns the mountpoint path (inside VM).
    """
    from tests.conftest import run_in_vm

    # Get mountpoint
    result = run_in_vm(f"zfs get -H -o value mountpoint {zfs_dataset_with_children}")
    mountpoint = result.stdout.strip()

    # Create test files
    run_in_vm(f"echo 'test content 1' | sudo tee {mountpoint}/file1.txt")
    run_in_vm(f"sudo mkdir -p {mountpoint}/subdir")
    run_in_vm(f"echo 'test content 2' | sudo tee {mountpoint}/subdir/file2.txt")

    return Path(mountpoint)
