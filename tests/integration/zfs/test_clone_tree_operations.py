"""
Tests for ZFS clone tree operations (Feature-44).

These tests verify the cloud_mirror.zfs module's clone tree functionality.
Requires Colima VM with testpool and CLOUD_MIRROR_USE_VM=1.

Tests are ordered trivial → complex for fast failure on issues.
"""

import logging
import uuid
from pathlib import Path

import pytest

from conftest import run_in_vm, TESTPOOL


@pytest.fixture
def logger() -> logging.Logger:
    """Create a logger for tests."""
    return logging.getLogger("test")


def dataset_exists(dataset: str) -> bool:
    """Check if a dataset exists."""
    result = run_in_vm(f"zfs list -H {dataset}")
    return result.returncode == 0


def get_dataset_property(dataset: str, prop: str) -> str | None:
    """Get a dataset property value."""
    result = run_in_vm(f"zfs get -H -o value {prop} {dataset}")
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def snapshot_exists(dataset: str, snap_name: str) -> bool:
    """Check if a snapshot exists."""
    result = run_in_vm(f"zfs list -H -t snapshot {dataset}@{snap_name}")
    return result.returncode == 0


# =============================================================================
# Story-32: Create Clone (Foundation)
# =============================================================================


class TestGetCloneDatasetName:
    """Tests for get_clone_dataset_name function."""

    def test_appends_suffix(self) -> None:
        """Should append .cloudmirror suffix."""
        from cloud_mirror.zfs import get_clone_dataset_name

        result = get_clone_dataset_name("testpool/data")
        assert result == "testpool/data.cloudmirror"

    def test_works_with_nested_dataset(self) -> None:
        """Should work with nested datasets."""
        from cloud_mirror.zfs import get_clone_dataset_name

        result = get_clone_dataset_name("testpool/data/child/grandchild")
        assert result == "testpool/data/child/grandchild.cloudmirror"


class TestGetCloneMountpoint:
    """Tests for get_clone_mountpoint function."""

    def test_appends_suffix_to_mountpoint(self) -> None:
        """Should append .cloudmirror suffix to mountpoint."""
        from cloud_mirror.zfs import get_clone_mountpoint

        result = get_clone_mountpoint(Path("/testpool/data"))
        assert result == Path("/testpool/data.cloudmirror")

    def test_works_with_nested_path(self) -> None:
        """Should work with nested paths."""
        from cloud_mirror.zfs import get_clone_mountpoint

        result = get_clone_mountpoint(Path("/mnt/apps/config"))
        assert result == Path("/mnt/apps/config.cloudmirror")


class TestGetPoolName:
    """Tests for get_pool_name function."""

    def test_extracts_pool_name(self) -> None:
        """Should extract pool name from dataset."""
        from cloud_mirror.zfs import get_pool_name

        assert get_pool_name("testpool/data") == "testpool"
        assert get_pool_name("testpool/data/child") == "testpool"
        assert get_pool_name("testpool") == "testpool"


class TestStripAltroot:
    """Tests for strip_altroot function."""

    def test_no_altroot_returns_unchanged(self) -> None:
        """Should return unchanged if no altroot."""
        from cloud_mirror.zfs import strip_altroot

        result = strip_altroot(Path("/testpool/data"), None)
        assert result == Path("/testpool/data")

    def test_strips_altroot_prefix(self) -> None:
        """Should strip altroot prefix and make absolute."""
        from cloud_mirror.zfs import strip_altroot

        result = strip_altroot(Path("/mnt/testpool/data"), Path("/mnt"))
        assert result == Path("/testpool/data")

    def test_non_matching_altroot_unchanged(self) -> None:
        """Should return unchanged if path doesn't start with altroot."""
        from cloud_mirror.zfs import strip_altroot

        result = strip_altroot(Path("/other/testpool/data"), Path("/mnt"))
        assert result == Path("/other/testpool/data")


class TestIsOurClone:
    """Tests for is_our_clone function."""

    @pytest.mark.vm_required
    def test_returns_true_for_managed_clone(
        self, zfs_dataset: str, logger: logging.Logger
    ) -> None:
        """Should return True for dataset with our management property."""
        from cloud_mirror.zfs import (
            is_our_clone,
            ZFS_MANAGED_PROPERTY,
            ZFS_MANAGED_VALUE,
        )

        # Set our management property (needs sudo in VM)
        run_in_vm(f"sudo zfs set {ZFS_MANAGED_PROPERTY}={ZFS_MANAGED_VALUE} {zfs_dataset}")

        assert is_our_clone(zfs_dataset, logger) is True

    @pytest.mark.vm_required
    def test_returns_false_for_unmanaged_dataset(
        self, zfs_dataset: str, logger: logging.Logger
    ) -> None:
        """Should return False for dataset without our property."""
        from cloud_mirror.zfs import is_our_clone

        # Fresh dataset without our property
        assert is_our_clone(zfs_dataset, logger) is False

    @pytest.mark.vm_required
    def test_returns_false_for_nonexistent_dataset(
        self, logger: logging.Logger
    ) -> None:
        """Should return False for non-existent dataset."""
        from cloud_mirror.zfs import is_our_clone

        assert is_our_clone(f"{TESTPOOL}/nonexistent-{uuid.uuid4().hex[:8]}", logger) is False


# =============================================================================
# Story-54: Clone Tree Creation
# =============================================================================


class TestCreateCloneTree:
    """Tests for create_clone_tree function."""

    @pytest.mark.vm_required
    def test_creates_clone_tree_with_children(
        self, zfs_dataset_with_children: str, logger: logging.Logger
    ) -> None:
        """Should create clones for root and all children (FI1)."""
        from cloud_mirror.zfs import (
            create_clone_tree,
            destroy_clone_tree,
            create_recursive_snapshot,
            destroy_recursive_snapshot,
            get_clone_dataset_name,
            get_clone_mountpoint,
            get_pool_altroot,
            get_pool_name,
            list_datasets_recursive,
            ZFS_MANAGED_PROPERTY,
            ZFS_MANAGED_VALUE,
        )

        root = zfs_dataset_with_children
        snap_name = f"test-{uuid.uuid4().hex[:8]}"
        clone_root = get_clone_dataset_name(root)

        # Get mountpoint for root dataset
        mp_result = run_in_vm(f"zfs get -H -o value mountpoint {root}")
        root_mountpoint = Path(mp_result.stdout.strip())
        clone_mountpoint = get_clone_mountpoint(root_mountpoint)

        pool = get_pool_name(root)
        altroot = get_pool_altroot(pool, logger)
        datasets = list_datasets_recursive(root, logger)

        try:
            # Create snapshot first
            create_recursive_snapshot(root, snap_name, logger)

            # Create clone tree
            create_clone_tree(
                root, datasets, snap_name, clone_root, clone_mountpoint, altroot, logger
            )

            # Verify all clones exist
            assert dataset_exists(clone_root)
            assert dataset_exists(f"{clone_root}/child1")
            assert dataset_exists(f"{clone_root}/child2")

            # Verify all clones have management property
            assert get_dataset_property(clone_root, ZFS_MANAGED_PROPERTY) == ZFS_MANAGED_VALUE
            assert get_dataset_property(f"{clone_root}/child1", ZFS_MANAGED_PROPERTY) == ZFS_MANAGED_VALUE
            assert get_dataset_property(f"{clone_root}/child2", ZFS_MANAGED_PROPERTY) == ZFS_MANAGED_VALUE

            # Verify all clones are readonly
            assert get_dataset_property(clone_root, "readonly") == "on"
            assert get_dataset_property(f"{clone_root}/child1", "readonly") == "on"
            assert get_dataset_property(f"{clone_root}/child2", "readonly") == "on"

        finally:
            # Cleanup
            destroy_clone_tree(clone_root, logger)
            destroy_recursive_snapshot(root, snap_name, logger)

    @pytest.mark.vm_required
    def test_clone_tree_accessible_as_filesystem(
        self, zfs_dataset_with_children: str, logger: logging.Logger
    ) -> None:
        """Should create accessible filesystem with files (FI2)."""
        from cloud_mirror.zfs import (
            create_clone_tree,
            destroy_clone_tree,
            create_recursive_snapshot,
            destroy_recursive_snapshot,
            get_clone_dataset_name,
            get_clone_mountpoint,
            get_pool_altroot,
            get_pool_name,
            list_datasets_recursive,
        )

        root = zfs_dataset_with_children
        snap_name = f"test-{uuid.uuid4().hex[:8]}"
        clone_root = get_clone_dataset_name(root)

        # Get mountpoint for root dataset
        mp_result = run_in_vm(f"zfs get -H -o value mountpoint {root}")
        root_mountpoint = Path(mp_result.stdout.strip())
        clone_mountpoint = get_clone_mountpoint(root_mountpoint)

        pool = get_pool_name(root)
        altroot = get_pool_altroot(pool, logger)
        datasets = list_datasets_recursive(root, logger)

        # Create a test file in the dataset and sync to ensure it's on disk
        run_in_vm(f"echo 'test content' | sudo tee {root_mountpoint}/testfile.txt && sync")

        try:
            create_recursive_snapshot(root, snap_name, logger)
            create_clone_tree(
                root, datasets, snap_name, clone_root, clone_mountpoint, altroot, logger
            )

            # Verify clone mountpoint is accessible (directory exists and is mounted)
            result = run_in_vm(f"ls -la {clone_mountpoint}")
            assert result.returncode == 0

            # Verify we can list the clone structure
            result = run_in_vm(f"find {clone_mountpoint} -maxdepth 2 -type d")
            assert result.returncode == 0
            assert str(clone_mountpoint) in result.stdout

        finally:
            destroy_clone_tree(clone_root, logger)
            destroy_recursive_snapshot(root, snap_name, logger)


# =============================================================================
# Story-76: Clone Tree Destruction
# =============================================================================


class TestDestroyCloneTree:
    """Tests for destroy_clone_tree function."""

    @pytest.mark.vm_required
    def test_destroys_clone_tree_recursively(
        self, zfs_dataset_with_children: str, logger: logging.Logger
    ) -> None:
        """Should destroy entire clone tree (FI3)."""
        from cloud_mirror.zfs import (
            create_clone_tree,
            destroy_clone_tree,
            create_recursive_snapshot,
            destroy_recursive_snapshot,
            get_clone_dataset_name,
            get_clone_mountpoint,
            get_pool_altroot,
            get_pool_name,
            list_datasets_recursive,
        )

        root = zfs_dataset_with_children
        snap_name = f"test-{uuid.uuid4().hex[:8]}"
        clone_root = get_clone_dataset_name(root)

        mp_result = run_in_vm(f"zfs get -H -o value mountpoint {root}")
        root_mountpoint = Path(mp_result.stdout.strip())
        clone_mountpoint = get_clone_mountpoint(root_mountpoint)

        pool = get_pool_name(root)
        altroot = get_pool_altroot(pool, logger)
        datasets = list_datasets_recursive(root, logger)

        try:
            create_recursive_snapshot(root, snap_name, logger)
            create_clone_tree(
                root, datasets, snap_name, clone_root, clone_mountpoint, altroot, logger
            )

            # Verify clones exist
            assert dataset_exists(clone_root)

            # Destroy clone tree
            destroy_clone_tree(clone_root, logger)

            # Verify all clones are gone
            assert not dataset_exists(clone_root)
            assert not dataset_exists(f"{clone_root}/child1")
            assert not dataset_exists(f"{clone_root}/child2")

        finally:
            destroy_recursive_snapshot(root, snap_name, logger)

    @pytest.mark.vm_required
    def test_refuses_to_destroy_non_managed_dataset(
        self, zfs_dataset: str, logger: logging.Logger
    ) -> None:
        """Should raise error for dataset without management property (FI4)."""
        from cloud_mirror.zfs import destroy_clone_tree, CloneNotOursError

        # Dataset exists but doesn't have our property
        with pytest.raises(CloneNotOursError) as exc_info:
            destroy_clone_tree(zfs_dataset, logger)

        assert zfs_dataset in str(exc_info.value)

    @pytest.mark.vm_required
    def test_handles_nonexistent_clone_gracefully(
        self, logger: logging.Logger
    ) -> None:
        """Should not raise error for non-existent clone tree."""
        from cloud_mirror.zfs import destroy_clone_tree

        # Should not raise
        destroy_clone_tree(f"{TESTPOOL}/nonexistent-{uuid.uuid4().hex[:8]}", logger)


class TestFindStaleClone:
    """Tests for find_stale_clone function."""

    @pytest.mark.vm_required
    def test_finds_stale_clone(
        self, zfs_dataset_with_children: str, logger: logging.Logger
    ) -> None:
        """Should find stale clone that has our property (FI5)."""
        from cloud_mirror.zfs import (
            create_clone_tree,
            destroy_clone_tree,
            create_recursive_snapshot,
            destroy_recursive_snapshot,
            find_stale_clone,
            get_clone_dataset_name,
            get_clone_mountpoint,
            get_pool_altroot,
            get_pool_name,
            list_datasets_recursive,
        )

        root = zfs_dataset_with_children
        snap_name = f"test-{uuid.uuid4().hex[:8]}"
        clone_root = get_clone_dataset_name(root)

        mp_result = run_in_vm(f"zfs get -H -o value mountpoint {root}")
        root_mountpoint = Path(mp_result.stdout.strip())
        clone_mountpoint = get_clone_mountpoint(root_mountpoint)

        pool = get_pool_name(root)
        altroot = get_pool_altroot(pool, logger)
        datasets = list_datasets_recursive(root, logger)

        try:
            create_recursive_snapshot(root, snap_name, logger)
            create_clone_tree(
                root, datasets, snap_name, clone_root, clone_mountpoint, altroot, logger
            )

            # Find stale clone
            stale = find_stale_clone(root, logger)
            assert stale == clone_root

        finally:
            destroy_clone_tree(clone_root, logger)
            destroy_recursive_snapshot(root, snap_name, logger)

    @pytest.mark.vm_required
    def test_returns_none_when_no_stale_clone(
        self, zfs_dataset: str, logger: logging.Logger
    ) -> None:
        """Should return None when no stale clone exists."""
        from cloud_mirror.zfs import find_stale_clone

        stale = find_stale_clone(zfs_dataset, logger)
        assert stale is None
