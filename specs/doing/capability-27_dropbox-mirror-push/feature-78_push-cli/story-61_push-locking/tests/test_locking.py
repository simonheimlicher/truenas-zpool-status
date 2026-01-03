"""
Integration tests for push locking.

Level 2 (Real Filesystem): Tests the filesystem-based locking mechanism
using fcntl.flock. These tests verify concurrent access prevention
without requiring the VM.

Testing Strategy:
- Uses tmp_path for lock directory (real filesystem, no mocks)
- Uses multiprocessing for concurrent lock testing
- Tests lock acquisition, contention, and release
"""

from __future__ import annotations

import multiprocessing
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cloud_mirror.push import (
    LockError,
    extract_pool_name,
    get_lock_directory,
    pool_lock,
)

if TYPE_CHECKING:
    from multiprocessing.synchronize import Barrier, Event


# =============================================================================
# Test Values (Part 0: Shared test data)
# =============================================================================


@dataclass(frozen=True)
class DatasetCase:
    """Test case for dataset/pool extraction."""

    dataset: str
    expected_pool: str


TYPICAL_DATASETS = {
    "SIMPLE": DatasetCase(dataset="testpool/data", expected_pool="testpool"),
    "NESTED": DatasetCase(dataset="tank/home/user/docs", expected_pool="tank"),
    "SINGLE": DatasetCase(dataset="rpool", expected_pool="rpool"),
}

EDGE_DATASETS = {
    "DEEP_NESTING": DatasetCase(
        dataset="pool/a/b/c/d/e/f",
        expected_pool="pool",
    ),
    "NUMERIC_NAME": DatasetCase(
        dataset="pool123/data",
        expected_pool="pool123",
    ),
    "HYPHENATED": DatasetCase(
        dataset="my-pool/my-data",
        expected_pool="my-pool",
    ),
}


# =============================================================================
# Part 1: Named Typical Cases
# =============================================================================


class TestPoolNameExtraction:
    """GIVEN typical dataset names."""

    def test_simple_dataset_extracts_pool(self) -> None:
        """WHEN extracting pool from SIMPLE dataset THEN returns first component."""
        case = TYPICAL_DATASETS["SIMPLE"]
        result = extract_pool_name(case.dataset)
        assert result == case.expected_pool

    def test_nested_dataset_extracts_pool(self) -> None:
        """WHEN extracting pool from NESTED dataset THEN returns first component."""
        case = TYPICAL_DATASETS["NESTED"]
        result = extract_pool_name(case.dataset)
        assert result == case.expected_pool

    def test_single_component_returns_itself(self) -> None:
        """WHEN extracting pool from pool-only name THEN returns the name."""
        case = TYPICAL_DATASETS["SINGLE"]
        result = extract_pool_name(case.dataset)
        assert result == case.expected_pool


class TestLockAcquisition:
    """GIVEN push operation starting."""

    def test_lock_acquired_creates_lock_file(self, tmp_path: Path) -> None:
        """WHEN acquiring lock THEN lock file is created."""
        with pool_lock("testpool/data", lock_dir=tmp_path) as lock_path:
            assert lock_path.exists()
            assert lock_path.name == "testpool.lock"

    def test_lock_file_contains_pid(self, tmp_path: Path) -> None:
        """WHEN lock acquired THEN lock file contains PID."""
        with pool_lock("testpool/data", lock_dir=tmp_path) as lock_path:
            content = lock_path.read_text()
            assert str(os.getpid()) in content

    def test_lock_directory_created_if_missing(self, tmp_path: Path) -> None:
        """WHEN lock directory doesn't exist THEN it is created."""
        nested_dir = tmp_path / "nested" / "lock" / "dir"
        assert not nested_dir.exists()

        with pool_lock("testpool/data", lock_dir=nested_dir):
            assert nested_dir.exists()


class TestLockRelease:
    """GIVEN push operation completing."""

    def test_lock_released_on_success(self, tmp_path: Path) -> None:
        """WHEN operation completes successfully THEN lock is released."""
        with pool_lock("testpool/data", lock_dir=tmp_path):
            pass  # Simulate successful operation

        # Should be able to acquire lock again
        with pool_lock("testpool/data", lock_dir=tmp_path):
            pass

    def test_lock_released_on_exception(self, tmp_path: Path) -> None:
        """WHEN operation fails with exception THEN lock is released."""
        with pytest.raises(ValueError, match="test error"):
            with pool_lock("testpool/data", lock_dir=tmp_path):
                raise ValueError("test error")

        # Should be able to acquire lock again
        with pool_lock("testpool/data", lock_dir=tmp_path):
            pass


# =============================================================================
# Part 2: Named Edge Cases
# =============================================================================


class TestEdgeCases:
    """GIVEN boundary conditions."""

    def test_deep_nesting_extracts_pool(self) -> None:
        """WHEN extracting from deeply nested dataset THEN returns first component."""
        case = EDGE_DATASETS["DEEP_NESTING"]
        result = extract_pool_name(case.dataset)
        assert result == case.expected_pool

    def test_numeric_pool_name(self) -> None:
        """WHEN pool name contains numbers THEN extracted correctly."""
        case = EDGE_DATASETS["NUMERIC_NAME"]
        result = extract_pool_name(case.dataset)
        assert result == case.expected_pool

    def test_hyphenated_pool_name(self) -> None:
        """WHEN pool name contains hyphens THEN extracted correctly."""
        case = EDGE_DATASETS["HYPHENATED"]
        result = extract_pool_name(case.dataset)
        assert result == case.expected_pool

    def test_different_datasets_same_pool_same_lock(self, tmp_path: Path) -> None:
        """WHEN different datasets in same pool THEN same lock file."""
        with pool_lock("testpool/data1", lock_dir=tmp_path) as lock1:
            pass

        with pool_lock("testpool/data2", lock_dir=tmp_path) as lock2:
            pass

        # Both should use the same lock file
        assert lock1 == lock2

    def test_different_pools_different_locks(self, tmp_path: Path) -> None:
        """WHEN different pools THEN different lock files."""
        with pool_lock("pool1/data", lock_dir=tmp_path) as lock1:
            with pool_lock("pool2/data", lock_dir=tmp_path) as lock2:
                # Should be able to hold both locks simultaneously
                assert lock1 != lock2
                assert lock1.name == "pool1.lock"
                assert lock2.name == "pool2.lock"


# =============================================================================
# Part 3: Systematic Coverage
# =============================================================================


class TestSystematicCoverage:
    """GIVEN all known dataset cases."""

    @pytest.mark.parametrize(
        ("name", "case"),
        list(TYPICAL_DATASETS.items()) + list(EDGE_DATASETS.items()),
    )
    def test_pool_extraction(self, name: str, case: DatasetCase) -> None:
        """WHEN testing all cases THEN pool extracted correctly."""
        result = extract_pool_name(case.dataset)
        assert result == case.expected_pool, f"Failed for case: {name}"


# =============================================================================
# Concurrent Lock Testing (FR2: Concurrent push fails immediately)
# =============================================================================


def _worker_acquire_lock(
    dataset: str,
    lock_dir: Path,
    barrier: Barrier,
    success_event: Event,
    hold_time: float,
) -> None:
    """Worker function that tries to acquire lock and signals result."""
    barrier.wait()  # Synchronize start

    try:
        with pool_lock(dataset, lock_dir=lock_dir):
            success_event.set()
            time.sleep(hold_time)
    except LockError:
        pass  # Expected for the loser


def _worker_hold_lock(
    dataset: str,
    lock_dir: Path,
    ready_event: Event,
    release_event: Event,
) -> None:
    """Worker function that holds lock until signaled to release."""
    with pool_lock(dataset, lock_dir=lock_dir):
        ready_event.set()  # Signal that lock is held
        release_event.wait()  # Wait for signal to release


class TestConcurrentLocking:
    """GIVEN concurrent push operations."""

    def test_second_operation_fails_with_lock_error(self, tmp_path: Path) -> None:
        """WHEN second push attempted on same pool THEN fails with LockError."""
        # Hold the lock in context
        with pool_lock("testpool/data", lock_dir=tmp_path):
            # Try to acquire same lock - should fail immediately
            with pytest.raises(LockError) as exc_info:
                with pool_lock("testpool/other", lock_dir=tmp_path):
                    pass

            # Verify error message
            assert "testpool" in str(exc_info.value)
            assert "another operation" in str(exc_info.value)

    def test_lock_error_contains_pool_name(self, tmp_path: Path) -> None:
        """WHEN LockError raised THEN contains pool name."""
        with pool_lock("mypool/dataset", lock_dir=tmp_path):
            with pytest.raises(LockError) as exc_info:
                with pool_lock("mypool/other", lock_dir=tmp_path):
                    pass

            assert exc_info.value.pool == "mypool"

    def test_lock_error_contains_lock_path(self, tmp_path: Path) -> None:
        """WHEN LockError raised THEN contains lock file path."""
        with pool_lock("mypool/dataset", lock_dir=tmp_path):
            with pytest.raises(LockError) as exc_info:
                with pool_lock("mypool/other", lock_dir=tmp_path):
                    pass

            assert exc_info.value.lock_path == tmp_path / "mypool.lock"

    def test_first_operation_continues_unaffected(self, tmp_path: Path) -> None:
        """WHEN second push fails THEN first operation continues."""
        operation_completed = False

        with pool_lock("testpool/data", lock_dir=tmp_path):
            # Second operation fails
            with pytest.raises(LockError):
                with pool_lock("testpool/other", lock_dir=tmp_path):
                    pass

            # First operation continues
            operation_completed = True

        assert operation_completed

    def test_concurrent_processes_one_wins(self, tmp_path: Path) -> None:
        """WHEN two processes race for lock THEN exactly one wins."""
        # Use multiprocessing to test real concurrent lock acquisition
        ctx = multiprocessing.get_context("spawn")
        barrier = ctx.Barrier(2)
        success1 = ctx.Event()
        success2 = ctx.Event()

        p1 = ctx.Process(
            target=_worker_acquire_lock,
            args=("testpool/data", tmp_path, barrier, success1, 0.5),
        )
        p2 = ctx.Process(
            target=_worker_acquire_lock,
            args=("testpool/other", tmp_path, barrier, success2, 0.5),
        )

        p1.start()
        p2.start()
        p1.join(timeout=5)
        p2.join(timeout=5)

        # Exactly one should have succeeded
        wins = int(success1.is_set()) + int(success2.is_set())
        assert wins == 1, f"Expected 1 winner, got {wins}"

    def test_lock_released_allows_next_process(self, tmp_path: Path) -> None:
        """WHEN first operation releases lock THEN next process can acquire."""
        ctx = multiprocessing.get_context("spawn")
        ready_event = ctx.Event()
        release_event = ctx.Event()

        # Start process that holds lock
        holder = ctx.Process(
            target=_worker_hold_lock,
            args=("testpool/data", tmp_path, ready_event, release_event),
        )
        holder.start()

        # Wait for holder to acquire lock
        ready_event.wait(timeout=5)

        # Verify we can't acquire
        with pytest.raises(LockError):
            with pool_lock("testpool/data", lock_dir=tmp_path):
                pass

        # Signal holder to release
        release_event.set()
        holder.join(timeout=5)

        # Now we should be able to acquire
        with pool_lock("testpool/data", lock_dir=tmp_path):
            pass


# =============================================================================
# Lock Directory Selection (FR4)
# =============================================================================


class TestLockDirectorySelection:
    """GIVEN lock directory selection."""

    def test_xdg_runtime_dir_preferred(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """WHEN XDG_RUNTIME_DIR set THEN uses it."""
        xdg_dir = tmp_path / "xdg-runtime"
        xdg_dir.mkdir()
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(xdg_dir))

        lock_dir = get_lock_directory()

        assert lock_dir == xdg_dir / "cloud-mirror"

    def test_fallback_to_cache_on_permission_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """WHEN XDG_RUNTIME_DIR not writable THEN falls back to cache."""
        # Set XDG to non-existent, non-creatable path
        monkeypatch.setenv("XDG_RUNTIME_DIR", "/nonexistent/path/that/cant/exist")

        lock_dir = get_lock_directory()

        # Should fall back to ~/.cache/cloud-mirror
        assert lock_dir == Path.home() / ".cache" / "cloud-mirror"

    def test_cache_directory_created(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """WHEN cache dir doesn't exist THEN it is created."""
        # Clear XDG so it falls through
        monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)

        # Patch Path.home to use tmp_path
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        lock_dir = get_lock_directory()

        assert lock_dir.exists()
        assert lock_dir == fake_home / ".cache" / "cloud-mirror"
