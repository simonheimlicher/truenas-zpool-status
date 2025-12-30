"""
Tests for ZFS snapshot operations (graduated from Feature-27).

These tests verify the cloud_mirror.zfs module's snapshot functionality.
Requires Colima VM with testpool and CLOUD_MIRROR_USE_VM=1.

Tests are ordered trivial → complex for fast failure on issues.
"""

import logging
import uuid

import pytest

from conftest import run_in_vm, TESTPOOL


@pytest.fixture
def logger() -> logging.Logger:
    """Create a logger for tests."""
    return logging.getLogger("test")


def snapshot_exists(dataset: str, snap_name: str) -> bool:
    """Check if a snapshot exists."""
    result = run_in_vm(f"zfs list -H -t snapshot {dataset}@{snap_name}")
    return result.returncode == 0


# =============================================================================
# Story-32: list_datasets_recursive
# =============================================================================


class TestListDatasetsRecursive:
    """Tests for list_datasets_recursive function (Story-32)."""

    @pytest.mark.vm_required
    def test_lists_root_and_children(
        self, zfs_dataset_with_children: str, logger: logging.Logger
    ) -> None:
        """Should return root and all child datasets."""
        from cloud_mirror.zfs import list_datasets_recursive

        root = zfs_dataset_with_children
        datasets = list_datasets_recursive(root, logger)

        assert len(datasets) == 3
        assert root in datasets
        assert f"{root}/child1" in datasets
        assert f"{root}/child2" in datasets

    @pytest.mark.vm_required
    def test_root_is_first(
        self, zfs_dataset_with_children: str, logger: logging.Logger
    ) -> None:
        """Root dataset should be first in returned list."""
        from cloud_mirror.zfs import list_datasets_recursive

        root = zfs_dataset_with_children
        datasets = list_datasets_recursive(root, logger)

        assert datasets[0] == root

    @pytest.mark.vm_required
    def test_single_dataset_no_children(
        self, zfs_dataset: str, logger: logging.Logger
    ) -> None:
        """Single dataset with no children returns just itself."""
        from cloud_mirror.zfs import list_datasets_recursive

        datasets = list_datasets_recursive(zfs_dataset, logger)

        assert datasets == [zfs_dataset]


# =============================================================================
# Story-54: create_recursive_snapshot
# =============================================================================


class TestCreateRecursiveSnapshot:
    """Tests for create_recursive_snapshot function (Story-54)."""

    @pytest.mark.vm_required
    def test_creates_snapshot_on_all_datasets(
        self, zfs_dataset_with_children: str, logger: logging.Logger
    ) -> None:
        """Should create snapshot on root and all children."""
        from cloud_mirror.zfs import create_recursive_snapshot, destroy_recursive_snapshot

        root = zfs_dataset_with_children
        snap_name = f"test-{uuid.uuid4().hex[:8]}"

        try:
            create_recursive_snapshot(root, snap_name, logger)

            assert snapshot_exists(root, snap_name)
            assert snapshot_exists(f"{root}/child1", snap_name)
            assert snapshot_exists(f"{root}/child2", snap_name)
        finally:
            destroy_recursive_snapshot(root, snap_name, logger)

    @pytest.mark.vm_required
    def test_cleans_stale_snapshot_before_creating(
        self, zfs_dataset_with_children: str, logger: logging.Logger
    ) -> None:
        """Should destroy stale snapshot before creating new one."""
        from cloud_mirror.zfs import create_recursive_snapshot, destroy_recursive_snapshot

        root = zfs_dataset_with_children
        snap_name = f"test-{uuid.uuid4().hex[:8]}"

        try:
            run_in_vm(f"sudo zfs snapshot -r {root}@{snap_name}")
            assert snapshot_exists(root, snap_name)

            create_recursive_snapshot(root, snap_name, logger)

            assert snapshot_exists(root, snap_name)
        finally:
            destroy_recursive_snapshot(root, snap_name, logger)

    @pytest.mark.vm_required
    def test_cleans_partial_stale_snapshots(
        self, zfs_dataset_with_children: str, logger: logging.Logger
    ) -> None:
        """Should clean orphaned child snapshots even if root has none."""
        from cloud_mirror.zfs import create_recursive_snapshot, destroy_recursive_snapshot

        root = zfs_dataset_with_children
        snap_name = f"test-{uuid.uuid4().hex[:8]}"

        try:
            run_in_vm(f"sudo zfs snapshot {root}/child1@{snap_name}")
            assert snapshot_exists(f"{root}/child1", snap_name)
            assert not snapshot_exists(root, snap_name)

            create_recursive_snapshot(root, snap_name, logger)

            assert snapshot_exists(root, snap_name)
            assert snapshot_exists(f"{root}/child1", snap_name)
            assert snapshot_exists(f"{root}/child2", snap_name)
        finally:
            destroy_recursive_snapshot(root, snap_name, logger)


# =============================================================================
# Story-76: destroy_recursive_snapshot
# =============================================================================


class TestDestroyRecursiveSnapshot:
    """Tests for destroy_recursive_snapshot function (Story-76)."""

    @pytest.mark.vm_required
    def test_destroys_snapshot_on_all_datasets(
        self, zfs_dataset_with_children: str, logger: logging.Logger
    ) -> None:
        """Should destroy snapshot on root and all children."""
        from cloud_mirror.zfs import destroy_recursive_snapshot

        root = zfs_dataset_with_children
        snap_name = f"test-{uuid.uuid4().hex[:8]}"

        run_in_vm(f"sudo zfs snapshot -r {root}@{snap_name}")
        assert snapshot_exists(root, snap_name)

        destroy_recursive_snapshot(root, snap_name, logger)

        assert not snapshot_exists(root, snap_name)
        assert not snapshot_exists(f"{root}/child1", snap_name)
        assert not snapshot_exists(f"{root}/child2", snap_name)

    @pytest.mark.vm_required
    def test_handles_nonexistent_snapshot_gracefully(
        self, zfs_dataset: str, logger: logging.Logger
    ) -> None:
        """Should not raise error if snapshot doesn't exist."""
        from cloud_mirror.zfs import destroy_recursive_snapshot

        destroy_recursive_snapshot(zfs_dataset, "nonexistent-snap", logger)

    @pytest.mark.vm_required
    def test_destroys_single_dataset_snapshot(
        self, zfs_dataset: str, logger: logging.Logger
    ) -> None:
        """Should work on single dataset with no children."""
        from cloud_mirror.zfs import destroy_recursive_snapshot

        snap_name = f"test-{uuid.uuid4().hex[:8]}"

        run_in_vm(f"sudo zfs snapshot {zfs_dataset}@{snap_name}")
        assert snapshot_exists(zfs_dataset, snap_name)

        destroy_recursive_snapshot(zfs_dataset, snap_name, logger)

        assert not snapshot_exists(zfs_dataset, snap_name)
