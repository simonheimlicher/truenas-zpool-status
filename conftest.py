"""
Root conftest.py - makes fixtures from tests/conftest.py available to specs/ tests.

This enables story tests in specs/doing/.../ to use the same fixtures
as graduated tests in tests/.
"""

# Import all fixtures and helpers from tests/conftest.py
from tests.conftest import (
    # Markers
    pytest_configure,
    # VM helpers
    vm_running,
    run_in_vm,
    run_zfs_in_vm,
    pool_exists,
    TESTPOOL,
    VM_PROFILE,
    # Fixtures
    ensure_vm_running,
    ensure_pool_exists,
    zfs_dataset,
    zfs_dataset_with_children,
    zfs_mountpoint,
    sample_files_in_tmp,
    test_remote,
    rclone_config,
)

# Re-export for pytest fixture discovery
__all__ = [
    "pytest_configure",
    "vm_running",
    "run_in_vm",
    "run_zfs_in_vm",
    "pool_exists",
    "TESTPOOL",
    "VM_PROFILE",
    "ensure_vm_running",
    "ensure_pool_exists",
    "zfs_dataset",
    "zfs_dataset_with_children",
    "zfs_mountpoint",
    "sample_files_in_tmp",
    "test_remote",
    "rclone_config",
]
