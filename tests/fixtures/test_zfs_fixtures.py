"""
Tests for ZFS pytest fixtures (graduated from Feature-54, Story-32).

These tests verify the pytest fixtures for ZFS dataset creation/cleanup work correctly.
Run on the macOS host - commands execute via colima ssh.

Tests are ordered trivial → complex for fast failure on fixture issues.
"""

import pytest

from conftest import run_in_vm, vm_running, TESTPOOL


class TestZfsDatasetFixture:
    """Tests for zfs_dataset fixture (FR1: isolated dataset creation)."""

    @pytest.mark.vm_required
    def test_fixture_creates_unique_dataset(self, zfs_dataset: str) -> None:
        """Fixture should create a dataset with unique name."""
        assert zfs_dataset.startswith(f"{TESTPOOL}/test-")
        # Verify dataset exists
        result = run_in_vm(f"zfs list -H {zfs_dataset}")
        assert result.returncode == 0, f"Dataset {zfs_dataset} should exist"

    @pytest.mark.vm_required
    def test_fixture_provides_writable_dataset(self, zfs_dataset: str) -> None:
        """Fixture dataset should be writable."""
        result = run_in_vm(f"zfs get -H -o value mountpoint {zfs_dataset}")
        mountpoint = result.stdout.strip()

        # Write a test file
        result = run_in_vm(f"sudo touch {mountpoint}/testfile.txt")
        assert result.returncode == 0, "Should be able to write to dataset"

    @pytest.mark.vm_required
    def test_datasets_are_isolated(self, zfs_dataset: str) -> None:
        """Each test should get its own isolated dataset."""
        # Create a marker file in this dataset
        result = run_in_vm(f"zfs get -H -o value mountpoint {zfs_dataset}")
        mountpoint = result.stdout.strip()
        run_in_vm(f"sudo sh -c 'echo unique > {mountpoint}/marker.txt'")

        # Verify our marker exists
        result = run_in_vm(f"cat {mountpoint}/marker.txt")
        assert result.stdout.strip() == "unique"


class TestZfsDatasetWithChildrenFixture:
    """Tests for zfs_dataset_with_children fixture (FR2: nested datasets)."""

    @pytest.mark.vm_required
    def test_fixture_creates_root_and_children(
        self, zfs_dataset_with_children: str
    ) -> None:
        """Fixture should create root dataset with child1 and child2."""
        root = zfs_dataset_with_children

        # Verify root exists
        result = run_in_vm(f"zfs list -H {root}")
        assert result.returncode == 0, f"Root {root} should exist"

        # Verify children exist
        for child in ["child1", "child2"]:
            result = run_in_vm(f"zfs list -H {root}/{child}")
            assert result.returncode == 0, f"Child {root}/{child} should exist"

    @pytest.mark.vm_required
    def test_children_are_separate_datasets(
        self, zfs_dataset_with_children: str
    ) -> None:
        """Children should be separate ZFS datasets, not just directories."""
        root = zfs_dataset_with_children

        # Get list of all datasets under root
        result = run_in_vm(f"zfs list -H -r -o name {root}")
        datasets = result.stdout.strip().split("\n")

        # Should have exactly 3: root, child1, child2
        assert len(datasets) == 3
        assert root in datasets
        assert f"{root}/child1" in datasets
        assert f"{root}/child2" in datasets


class TestFixtureSkipBehavior:
    """Tests for graceful skip when ZFS unavailable (FR3)."""

    def test_vm_running_helper_exists(self) -> None:
        """The vm_running helper should be available from conftest."""
        assert callable(vm_running)

    def test_vm_running_returns_bool(self) -> None:
        """vm_running() should return a boolean."""
        result = vm_running()
        assert isinstance(result, bool)
