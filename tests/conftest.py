"""
Pytest fixtures for ZFS and rclone testing.

Test Categories:
- Unit tests: Run anywhere (no ZFS needed) - direction detection, validation
- ZFS tests: Require ZFS kernel modules - run on TrueNAS or Linux with ZFS

Usage:
  # Run unit tests only (Docker or local)
  pytest tests/ -m "not zfs"

  # Run all tests (requires ZFS)
  pytest tests/

  # Run ZFS tests only
  pytest tests/ -m zfs
"""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from typing import Generator

import pytest

# Pool name for ZFS tests (create with: zpool create testpool /path/to/file)
TESTPOOL = "testpool"


def pytest_configure(config: pytest.Config) -> None:
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers", "zfs: mark test as requiring ZFS (deselect with '-m \"not zfs\"')"
    )


def _run_zfs(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a ZFS command."""
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=check,
    )


def _is_zfs_available() -> bool:
    """Check if ZFS is available."""
    result = subprocess.run(
        ["which", "zfs"],
        capture_output=True,
    )
    if result.returncode != 0:
        return False

    # Check if ZFS modules are loaded
    result = _run_zfs(["zpool", "list"], check=False)
    return result.returncode == 0


@pytest.fixture
def zfs_dataset() -> Generator[str, None, None]:
    """
    Create an isolated ZFS dataset for testing.

    Yields the dataset name (e.g., 'testpool/test-abc123').
    The dataset is automatically destroyed after the test.

    Note: Tests using this fixture should be marked with @pytest.mark.zfs
    """
    if not _is_zfs_available():
        pytest.skip(f"ZFS not available (requires kernel modules)")

    # Check if testpool exists
    result = _run_zfs(["zfs", "list", "-H", TESTPOOL], check=False)
    if result.returncode != 0:
        pytest.skip(f"ZFS pool '{TESTPOOL}' not found")

    # Create unique dataset name to avoid conflicts
    dataset_id = uuid.uuid4().hex[:8]
    dataset_name = f"{TESTPOOL}/test-{dataset_id}"

    # Create the dataset
    _run_zfs(["zfs", "create", dataset_name])

    try:
        yield dataset_name
    finally:
        # Cleanup: destroy dataset and all children
        _run_zfs(["zfs", "destroy", "-rf", dataset_name], check=False)


@pytest.fixture
def zfs_dataset_with_children() -> Generator[str, None, None]:
    """
    Create a ZFS dataset with child datasets for testing nested operations.

    Yields the root dataset name. Structure:
        testpool/test-xxx/
        testpool/test-xxx/child1/
        testpool/test-xxx/child2/

    Note: Tests using this fixture should be marked with @pytest.mark.zfs
    """
    if not _is_zfs_available():
        pytest.skip(f"ZFS not available (requires kernel modules)")

    # Check if testpool exists
    result = _run_zfs(["zfs", "list", "-H", TESTPOOL], check=False)
    if result.returncode != 0:
        pytest.skip(f"ZFS pool '{TESTPOOL}' not found")

    dataset_id = uuid.uuid4().hex[:8]
    root_dataset = f"{TESTPOOL}/test-{dataset_id}"

    # Create root and children
    _run_zfs(["zfs", "create", root_dataset])
    _run_zfs(["zfs", "create", f"{root_dataset}/child1"])
    _run_zfs(["zfs", "create", f"{root_dataset}/child2"])

    try:
        yield root_dataset
    finally:
        _run_zfs(["zfs", "destroy", "-rf", root_dataset], check=False)


@pytest.fixture
def zfs_mountpoint(zfs_dataset: str) -> Path:
    """
    Get the mountpoint of a ZFS dataset.

    Depends on zfs_dataset fixture.
    """
    result = _run_zfs(
        ["zfs", "get", "-H", "-o", "value", "mountpoint", zfs_dataset]
    )
    return Path(result.stdout.strip())


@pytest.fixture
def sample_files(zfs_mountpoint: Path) -> Path:
    """
    Create sample files in a ZFS dataset for sync testing.

    Creates:
        file1.txt
        subdir/file2.txt
        symlink.txt -> file1.txt

    Returns the mountpoint path.
    """
    # Create files
    (zfs_mountpoint / "file1.txt").write_text("content of file 1\n")

    subdir = zfs_mountpoint / "subdir"
    subdir.mkdir()
    (subdir / "file2.txt").write_text("content of file 2\n")

    # Create symlink
    symlink = zfs_mountpoint / "symlink.txt"
    symlink.symlink_to("file1.txt")

    return zfs_mountpoint


@pytest.fixture
def sample_files_in_tmp(tmp_path: Path) -> Path:
    """
    Create sample files in a temporary directory (no ZFS needed).

    Creates:
        file1.txt
        subdir/file2.txt
        symlink.txt -> file1.txt

    Returns the temp directory path.
    """
    # Create files
    (tmp_path / "file1.txt").write_text("content of file 1\n")

    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "file2.txt").write_text("content of file 2\n")

    # Create symlink
    symlink = tmp_path / "symlink.txt"
    symlink.symlink_to("file1.txt")

    return tmp_path


@pytest.fixture
def test_remote(tmp_path: Path) -> str:
    """
    Create a local rclone 'remote' for testing.

    Uses rclone's local backend configured in tests/rclone-test.conf.
    Returns the rclone remote path (e.g., 'testremote:/tmp/pytest-xxx/remote').
    """
    remote_dir = tmp_path / "remote"
    remote_dir.mkdir()
    return f"testremote:{remote_dir}"


@pytest.fixture
def rclone_config() -> Path:
    """Return path to test rclone configuration."""
    config_path = Path(__file__).parent / "rclone-test.conf"
    if not config_path.exists():
        pytest.skip("rclone-test.conf not found")
    return config_path
