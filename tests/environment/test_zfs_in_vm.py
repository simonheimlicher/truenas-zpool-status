"""
Tests for ZFS installation in Colima VM (graduated from Story-54).

These tests verify ZFS is installed and working in the VM.
Run on the macOS host - commands execute via colima ssh.

Tests are ordered trivial → complex for fast failure on environment issues.
"""

from __future__ import annotations

import subprocess

import pytest


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


@pytest.fixture
def ensure_vm_running() -> None:
    """Skip test if VM is not running."""
    if not _vm_running():
        pytest.skip("VM not running. Start with: ./scripts/start-test-vm.sh")


@pytest.mark.vm_required
class TestZFSInstallation:
    """Tests for ZFS tools installed in VM (FR1)."""

    def test_zfs_command_available(self, ensure_vm_running: None) -> None:
        """zfs command should be available in the VM."""
        result = _run_in_vm("which zfs")
        assert result.returncode == 0, (
            f"zfs not found. Install with: ./scripts/setup-zfs-vm.sh\n"
            f"stderr: {result.stderr}"
        )
        assert "/zfs" in result.stdout.lower()

    def test_zpool_command_available(self, ensure_vm_running: None) -> None:
        """zpool command should be available in the VM."""
        result = _run_in_vm("which zpool")
        assert result.returncode == 0, (
            f"zpool not found. Install with: ./scripts/setup-zfs-vm.sh\n"
            f"stderr: {result.stderr}"
        )
        assert "/zpool" in result.stdout.lower()


@pytest.mark.vm_required
class TestZFSKernelModules:
    """Tests for ZFS kernel modules loaded (FR2)."""

    def test_zpool_list_succeeds(self, ensure_vm_running: None) -> None:
        """zpool list should succeed (kernel modules loaded)."""
        result = _run_in_vm("zpool list")
        # Exit 0 even if no pools exist
        assert result.returncode == 0, (
            f"zpool list failed - kernel modules may not be loaded.\n"
            f"stderr: {result.stderr}"
        )

    def test_zfs_module_loaded(self, ensure_vm_running: None) -> None:
        """ZFS kernel module should be loaded."""
        result = _run_in_vm("lsmod | grep -i zfs")
        assert result.returncode == 0, (
            "ZFS kernel module not loaded. Try: sudo modprobe zfs"
        )
        assert "zfs" in result.stdout.lower()
