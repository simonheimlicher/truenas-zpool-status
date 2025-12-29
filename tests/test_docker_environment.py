"""
Smoke tests for test environment.

Test Categories:
- Unit tests (no ZFS): Run in Docker or locally
- ZFS tests: Run only on systems with ZFS kernel modules

Run unit tests only:
  pytest tests/ -m "not zfs"

Run all tests (requires ZFS):
  pytest tests/
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


@pytest.mark.zfs
class TestZfsPool:
    """Tests for ZFS pool availability (requires ZFS kernel modules)."""

    def test_zfs_command_available(self) -> None:
        """ZFS command should be available."""
        result = subprocess.run(
            ["zfs", "version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_zpool_list(self) -> None:
        """zpool list should work."""
        result = subprocess.run(
            ["zpool", "list"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_can_create_dataset(self, zfs_dataset: str) -> None:
        """Should be able to create a dataset."""
        result = subprocess.run(
            ["zfs", "list", "-H", zfs_dataset],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert zfs_dataset in result.stdout

    def test_can_create_files(self, zfs_mountpoint: Path) -> None:
        """Should be able to create files in dataset."""
        test_file = zfs_mountpoint / "test.txt"
        test_file.write_text("hello world")
        assert test_file.exists()
        assert test_file.read_text() == "hello world"

    def test_can_create_snapshot(self, zfs_dataset: str) -> None:
        """Should be able to create snapshots."""
        snapshot_name = f"{zfs_dataset}@test-snap"
        result = subprocess.run(
            ["zfs", "snapshot", snapshot_name],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # Verify snapshot exists
        result = subprocess.run(
            ["zfs", "list", "-t", "snapshot", "-H", snapshot_name],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # Cleanup
        subprocess.run(["zfs", "destroy", snapshot_name], check=False)

    def test_sample_files_fixture(self, sample_files: Path) -> None:
        """sample_files fixture should create expected files in ZFS dataset."""
        assert (sample_files / "file1.txt").exists()
        assert (sample_files / "subdir" / "file2.txt").exists()
        assert (sample_files / "symlink.txt").is_symlink()

    def test_zfs_dataset_with_children_fixture(
        self, zfs_dataset_with_children: str
    ) -> None:
        """zfs_dataset_with_children should create nested datasets."""
        result = subprocess.run(
            ["zfs", "list", "-r", "-H", "-o", "name", zfs_dataset_with_children],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        datasets = result.stdout.strip().split("\n")
        assert len(datasets) == 3  # root + 2 children
        assert f"{zfs_dataset_with_children}/child1" in datasets
        assert f"{zfs_dataset_with_children}/child2" in datasets
