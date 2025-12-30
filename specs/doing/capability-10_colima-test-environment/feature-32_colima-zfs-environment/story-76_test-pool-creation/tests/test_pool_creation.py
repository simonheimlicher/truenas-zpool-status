"""
Tests for test pool creation (Story 76).

These tests verify the test ZFS pool is created and functional.
Run on the macOS host - commands execute via colima ssh.
"""

from __future__ import annotations

import subprocess

import pytest


POOL_NAME = "testpool"


def _run_in_vm(command: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    """Execute a command inside the Colima VM."""
    return subprocess.run(
        ["colima", "ssh", "--profile", "zfs-test", "--", "bash", "-c", command],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _vm_running() -> bool:
    """Check if the Colima VM is running."""
    # Note: colima status outputs to stderr, not stdout
    result = subprocess.run(
        ["colima", "status", "--profile", "zfs-test"],
        capture_output=True,
        text=True,
    )
    combined_output = (result.stdout + result.stderr).lower()
    return result.returncode == 0 and "is running" in combined_output


def _pool_exists() -> bool:
    """Check if testpool exists."""
    result = _run_in_vm(f"zpool list {POOL_NAME}")
    return result.returncode == 0


@pytest.fixture
def ensure_vm_running() -> None:
    """Skip test if VM is not running."""
    if not _vm_running():
        pytest.skip("VM not running. Start with: ./scripts/start-test-vm.sh")


@pytest.fixture
def ensure_pool_exists(ensure_vm_running: None) -> None:
    """Skip test if testpool doesn't exist."""
    if not _pool_exists():
        pytest.skip(
            f"Pool '{POOL_NAME}' not found. "
            f"Create with: ./scripts/create-test-pool.sh"
        )


@pytest.mark.vm_required
class TestPoolCreation:
    """Tests for FR1: Test pool created from loopback file."""

    def test_pool_exists(self, ensure_vm_running: None) -> None:
        """testpool should exist after running create script."""
        if not _pool_exists():
            pytest.fail(
                f"Pool '{POOL_NAME}' not found. "
                f"Create with: ./scripts/create-test-pool.sh"
            )

    def test_pool_is_healthy(self, ensure_pool_exists: None) -> None:
        """testpool should be in healthy state."""
        result = _run_in_vm(f"zpool status {POOL_NAME}")
        assert result.returncode == 0
        assert "ONLINE" in result.stdout, "Pool should be ONLINE"
        # Check no errors
        assert "DEGRADED" not in result.stdout
        assert "FAULTED" not in result.stdout

    def test_pool_file_exists(self, ensure_pool_exists: None) -> None:
        """Loopback file should exist."""
        result = _run_in_vm("ls -la /zfs-test/testpool.img")
        assert result.returncode == 0, "Pool file not found"


@pytest.mark.vm_required
class TestDatasetOperations:
    """Tests for FR3 and FR4: Multiple datasets and cleanup."""

    def test_can_create_dataset(self, ensure_pool_exists: None) -> None:
        """Should be able to create a dataset in testpool."""
        dataset = f"{POOL_NAME}/pytest-test-create"

        # Clean up first if exists
        _run_in_vm(f"sudo zfs destroy -r {dataset} 2>/dev/null || true")

        # Create dataset
        result = _run_in_vm(f"sudo zfs create {dataset}")
        assert result.returncode == 0, f"Failed to create dataset: {result.stderr}"

        # Verify exists
        result = _run_in_vm(f"zfs list {dataset}")
        assert result.returncode == 0, "Dataset should exist after creation"

        # Clean up
        _run_in_vm(f"sudo zfs destroy -r {dataset}")

    def test_can_create_multiple_datasets(self, ensure_pool_exists: None) -> None:
        """Should be able to create multiple isolated datasets."""
        datasets = [
            f"{POOL_NAME}/pytest-multi-a",
            f"{POOL_NAME}/pytest-multi-b",
        ]

        try:
            # Clean up first
            for ds in datasets:
                _run_in_vm(f"sudo zfs destroy -r {ds} 2>/dev/null || true")

            # Create all
            for ds in datasets:
                result = _run_in_vm(f"sudo zfs create {ds}")
                assert result.returncode == 0, f"Failed to create {ds}"

            # Verify all exist
            result = _run_in_vm(f"zfs list -r {POOL_NAME}")
            for ds in datasets:
                assert ds in result.stdout, f"{ds} should exist"

        finally:
            # Clean up
            for ds in datasets:
                _run_in_vm(f"sudo zfs destroy -r {ds} 2>/dev/null || true")

    def test_destroy_one_preserves_other(self, ensure_pool_exists: None) -> None:
        """Destroying one dataset should not affect siblings."""
        ds_a = f"{POOL_NAME}/pytest-destroy-a"
        ds_b = f"{POOL_NAME}/pytest-destroy-b"

        try:
            # Clean up and create
            _run_in_vm(f"sudo zfs destroy -r {ds_a} 2>/dev/null || true")
            _run_in_vm(f"sudo zfs destroy -r {ds_b} 2>/dev/null || true")
            _run_in_vm(f"sudo zfs create {ds_a}")
            _run_in_vm(f"sudo zfs create {ds_b}")

            # Destroy A
            result = _run_in_vm(f"sudo zfs destroy {ds_a}")
            assert result.returncode == 0

            # B should still exist
            result = _run_in_vm(f"zfs list {ds_b}")
            assert result.returncode == 0, "Dataset B should still exist"

        finally:
            _run_in_vm(f"sudo zfs destroy -r {ds_a} 2>/dev/null || true")
            _run_in_vm(f"sudo zfs destroy -r {ds_b} 2>/dev/null || true")
