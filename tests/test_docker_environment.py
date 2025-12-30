"""
Smoke tests for development environment.

These tests verify the development environment is set up correctly.
They do NOT require ZFS or the Colima VM to be running.

For ZFS environment tests, see tests/environment/
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


class TestEnvironment:
    """Tests for basic environment setup (no ZFS required)."""

    def test_rclone_command_available(self) -> None:
        """rclone command should be available."""
        result = subprocess.run(
            ["rclone", "version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "rclone" in result.stdout.lower()

    def test_python_version(self) -> None:
        """Python 3.11+ should be available."""
        import sys

        assert sys.version_info >= (3, 11)


class TestRcloneConfig:
    """Tests for rclone configuration (no ZFS required)."""

    def test_rclone_config_exists(self, rclone_config: Path) -> None:
        """Test rclone config file exists."""
        assert rclone_config.exists()

    def test_testremote_configured(self, rclone_config: Path) -> None:
        """testremote should be configured in rclone config."""
        result = subprocess.run(
            ["rclone", "--config", str(rclone_config), "listremotes"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "testremote:" in result.stdout


class TestFixtures:
    """Tests for pytest fixtures (no ZFS required)."""

    def test_test_remote_fixture(self, test_remote: str) -> None:
        """test_remote fixture should return valid rclone path."""
        assert test_remote.startswith("testremote:")
        # Extract path and verify it exists
        path = test_remote.split(":", 1)[1]
        assert Path(path).exists()

    def test_sample_files_in_tmp_fixture(self, sample_files_in_tmp: Path) -> None:
        """sample_files_in_tmp fixture should create expected files."""
        assert (sample_files_in_tmp / "file1.txt").exists()
        assert (sample_files_in_tmp / "subdir" / "file2.txt").exists()
        assert (sample_files_in_tmp / "symlink.txt").is_symlink()
