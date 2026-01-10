"""
Pytest fixtures for ZFS, rclone, and git testing.

IMPORTANT: Development vs Production Environment
- Development (macOS): ZFS runs inside Colima VM, accessed via SSH
- Production (TrueNAS SCALE): ZFS is native, no Colima

All ZFS fixtures execute commands inside the Colima VM via SSH.
Tests are dev-only infrastructure and never run in production.

Test Categories:
- Unit tests: Run anywhere (no ZFS needed) - direction detection, validation
- VM tests: Require Colima VM running with ZFS installed
- Internet tests: Require DROPBOX_TEST_TOKEN for real Dropbox (Level 3)
- Git tests: Use real git fixtures in tmp_path (not mocks)

Usage:
  # Run all tests (some may skip if VM not running)
  uv run --extra dev pytest tests/ -v

  # Run only non-VM tests
  uv run --extra dev pytest tests/ -v -m "not vm_required"

  # Run VM tests only (requires VM with testpool)
  uv run --extra dev pytest tests/ -v -m "vm_required"

  # Run Dropbox tests (requires DROPBOX_TEST_TOKEN in .env)
  uv run --extra dev pytest tests/ -v -m "internet_required"
"""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path
from typing import Generator

import pytest

from tests.fixtures.git_fixtures import GitRepo, with_git_repo

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, rely on environment variables

# Pool name for ZFS tests
TESTPOOL = "testpool"

# Colima VM profile for ZFS testing
VM_PROFILE = "zfs-test"


def pytest_configure(config: pytest.Config) -> None:
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers", "zfs: mark test as requiring ZFS (deselect with '-m \"not zfs\"')"
    )
    config.addinivalue_line(
        "markers",
        "vm_required: mark test as requiring Colima VM to be running",
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow-running"
    )
    config.addinivalue_line(
        "markers",
        "internet_required: mark test as requiring internet and DROPBOX_TEST_TOKEN",
    )


# =============================================================================
# VM Helpers - Shared utilities for running commands in Colima VM
# =============================================================================


def vm_running() -> bool:
    """
    Check if the Colima VM is running.

    Note: colima status outputs to stderr, not stdout.
    """
    result = subprocess.run(
        ["colima", "status", "--profile", VM_PROFILE],
        capture_output=True,
        text=True,
    )
    combined_output = (result.stdout + result.stderr).lower()
    return result.returncode == 0 and "is running" in combined_output


def run_in_vm(
    command: str, timeout: int = 30, check: bool = False
) -> subprocess.CompletedProcess[str]:
    """
    Execute a command inside the Colima VM via SSH.

    Args:
        command: Shell command to run in VM
        timeout: Command timeout in seconds
        check: If True, raise on non-zero exit

    Returns:
        CompletedProcess with stdout, stderr, returncode
    """
    return subprocess.run(
        ["colima", "ssh", "--profile", VM_PROFILE, "--", "bash", "-c", command],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
    )


def run_zfs_in_vm(
    args: list[str], check: bool = True
) -> subprocess.CompletedProcess[str]:
    """
    Run a ZFS command inside the Colima VM.

    Args:
        args: ZFS command and arguments (e.g., ["zfs", "list", "-H", "testpool"])
        check: If True, raise on non-zero exit

    Returns:
        CompletedProcess with stdout, stderr, returncode
    """
    command = " ".join(args)
    return run_in_vm(command, check=check)


def pool_exists() -> bool:
    """Check if testpool exists in the VM."""
    result = run_in_vm(f"zpool list {TESTPOOL}")
    return result.returncode == 0


# =============================================================================
# Fixtures - VM availability
# =============================================================================


@pytest.fixture
def ensure_vm_running() -> None:
    """Skip test if Colima VM is not running."""
    if not vm_running():
        pytest.skip(
            f"Colima VM not running. Start with: ./scripts/start-test-vm.sh"
        )


@pytest.fixture
def ensure_pool_exists(ensure_vm_running: None) -> None:
    """Skip test if testpool doesn't exist in VM."""
    if not pool_exists():
        pytest.skip(
            f"Pool '{TESTPOOL}' not found. Create with: ./scripts/create-test-pool.sh"
        )


# =============================================================================
# Fixtures - ZFS datasets (run in VM)
# =============================================================================


@pytest.fixture
def zfs_dataset(ensure_pool_exists: None) -> Generator[str, None, None]:
    """
    Create an isolated ZFS dataset for testing inside the Colima VM.

    Yields the dataset name (e.g., 'testpool/test-abc123').
    The dataset is automatically destroyed after the test.

    Note: Tests using this fixture should be marked with @pytest.mark.vm_required
    """
    # Create unique dataset name to avoid conflicts
    dataset_id = uuid.uuid4().hex[:8]
    dataset_name = f"{TESTPOOL}/test-{dataset_id}"

    # Create the dataset in VM
    result = run_in_vm(f"sudo zfs create {dataset_name}")
    if result.returncode != 0:
        pytest.fail(f"Failed to create dataset: {result.stderr}")

    try:
        yield dataset_name
    finally:
        # Cleanup: destroy dataset and all children
        run_in_vm(f"sudo zfs destroy -rf {dataset_name}")


@pytest.fixture
def zfs_dataset_with_children(
    ensure_pool_exists: None,
) -> Generator[str, None, None]:
    """
    Create a ZFS dataset with child datasets inside the Colima VM.

    Yields the root dataset name. Structure:
        testpool/test-xxx/
        testpool/test-xxx/child1/
        testpool/test-xxx/child2/

    Note: Tests using this fixture should be marked with @pytest.mark.vm_required
    """
    dataset_id = uuid.uuid4().hex[:8]
    root_dataset = f"{TESTPOOL}/test-{dataset_id}"

    # Create root and children in VM
    run_in_vm(f"sudo zfs create {root_dataset}")
    run_in_vm(f"sudo zfs create {root_dataset}/child1")
    run_in_vm(f"sudo zfs create {root_dataset}/child2")

    try:
        yield root_dataset
    finally:
        run_in_vm(f"sudo zfs destroy -rf {root_dataset}")


@pytest.fixture
def zfs_mountpoint(zfs_dataset: str) -> str:
    """
    Get the mountpoint of a ZFS dataset inside the VM.

    Returns the mountpoint path as a string (it's inside the VM, not local).
    """
    result = run_in_vm(f"zfs get -H -o value mountpoint {zfs_dataset}")
    return result.stdout.strip()


# =============================================================================
# Fixtures - Sample files (no ZFS needed)
# =============================================================================


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


# =============================================================================
# Fixtures - rclone
# =============================================================================


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


# =============================================================================
# Fixtures - Dropbox (Level 3 - Internet Required)
# =============================================================================


def get_dropbox_token() -> str | None:
    """Get Dropbox test token from environment."""
    return os.environ.get("DROPBOX_TEST_TOKEN")


@pytest.fixture
def dropbox_token() -> str:
    """
    Get Dropbox test token, skip if not available.

    The token should be set in .env file or DROPBOX_TEST_TOKEN environment variable.
    Get it by running: rclone authorize "dropbox"
    """
    token = get_dropbox_token()
    if not token:
        pytest.skip(
            "DROPBOX_TEST_TOKEN not set. "
            "Run 'rclone authorize dropbox' and add token to .env file."
        )
    return token


@pytest.fixture
def dropbox_config(tmp_path: Path, dropbox_token: str) -> Path:
    """
    Create temporary rclone config with real Dropbox credentials.

    Returns path to the config file.
    """
    config_path = tmp_path / "rclone-dropbox.conf"
    config_path.write_text(f"""[dropbox-test]
type = dropbox
token = {dropbox_token}
""")
    return config_path


@pytest.fixture
def dropbox_test_folder(
    dropbox_config: Path,
) -> Generator[str, None, None]:
    """
    Create an isolated test folder on Dropbox.

    Yields the rclone remote path (e.g., 'dropbox-test:cloud-mirror-test/test_abc123').
    The folder is automatically deleted after the test.

    Note: Tests using this fixture should be marked with @pytest.mark.internet_required
    """
    folder_id = uuid.uuid4().hex[:8]
    remote_path = f"dropbox-test:cloud-mirror-test/test_{folder_id}"

    # Create the test folder
    result = subprocess.run(
        ["rclone", "mkdir", remote_path, "--config", str(dropbox_config)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        pytest.fail(f"Failed to create Dropbox test folder: {result.stderr}")

    try:
        yield remote_path
    finally:
        # Cleanup: delete test folder and all contents
        subprocess.run(
            ["rclone", "purge", remote_path, "--config", str(dropbox_config)],
            capture_output=True,
            timeout=60,
        )


# =============================================================================
# Fixtures - Git (for update testing)
# =============================================================================


@pytest.fixture
def git_repo(tmp_path: Path) -> Generator[GitRepo, None, None]:
    """Provide a git repository fixture for tests.

    Creates a temporary git repository in tmp_path with initial setup.
    Uses real git commands (not mocks) per ADR-003.

    Example:
        def test_git_operations(git_repo):
            git_repo.create_commit("Test", {"file.txt": "content"})
            git_repo.create_tag("v1.0.0")
            assert git_repo.current_branch() == "main"
    """
    with with_git_repo(tmp_path) as repo:
        yield repo
