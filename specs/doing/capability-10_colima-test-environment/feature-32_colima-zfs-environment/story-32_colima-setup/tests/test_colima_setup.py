"""
Tests for Colima setup (Story 32).

These tests verify Colima is installed and the VM can be started.
Run on the macOS host (not inside the VM).
"""

from __future__ import annotations

import shutil
import subprocess

import pytest


class TestColimaInstallation:
    """Tests for FR1: Colima installed and configured."""

    def test_colima_command_available(self) -> None:
        """Colima should be installed and available in PATH."""
        colima_path = shutil.which("colima")
        assert colima_path is not None, (
            "colima not found in PATH. Install with: brew install colima"
        )

    def test_lima_dependency_installed(self) -> None:
        """Lima should be installed as Colima dependency."""
        lima_path = shutil.which("limactl")
        assert lima_path is not None, (
            "limactl not found. Lima should be installed with Colima."
        )


class TestColimaVMStatus:
    """Tests for FR2 and FR3: VM can be started and accessed."""

    @pytest.mark.slow
    def test_colima_status_command_works(self) -> None:
        """colima status should run without error (even if VM not running)."""
        result = subprocess.run(
            ["colima", "status", "--profile", "zfs-test"],
            capture_output=True,
            text=True,
        )
        # Status command should succeed even if VM is not running
        # It exits 0 if running, non-zero with message if not
        assert result.returncode in (0, 1), f"Unexpected error: {result.stderr}"

    @pytest.mark.slow
    @pytest.mark.vm_required
    def test_vm_running_and_accessible(self) -> None:
        """If VM is running, we should be able to SSH into it."""
        # First check if VM is running
        status = subprocess.run(
            ["colima", "status", "--profile", "zfs-test"],
            capture_output=True,
            text=True,
        )
        if status.returncode != 0 or "is running" not in status.stdout.lower():
            pytest.skip("VM not running. Start with: ./scripts/start-test-vm.sh")

        # Try to execute a command in the VM
        result = subprocess.run(
            ["colima", "ssh", "--profile", "zfs-test", "--", "uname", "-a"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"SSH failed: {result.stderr}"
        assert "Linux" in result.stdout, "Expected Linux kernel in VM"
