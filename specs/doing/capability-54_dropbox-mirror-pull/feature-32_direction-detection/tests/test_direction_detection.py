"""
Level 1 Unit Tests: Direction Detection.

Tests for detecting sync direction (PUSH or PULL) based on argument order.
rclone remotes (containing colon) are distinguished from ZFS datasets.

Test Levels:
- Level 1 (Unit): All tests in this file - pure Python, no external deps
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


# =============================================================================
# Test Values - Pattern for systematic testing
# =============================================================================


@dataclass(frozen=True)
class RemoteTestCase:
    """Test case for remote detection."""

    arg: str
    is_remote: bool
    reason: str


TYPICAL_REMOTES = {
    "DROPBOX": RemoteTestCase("dropbox:path", True, "standard remote"),
    "S3": RemoteTestCase("s3:bucket/key", True, "S3 bucket path"),
    "REMOTE_ONLY": RemoteTestCase("remote:", True, "remote without path"),
    "UNDERSCORE": RemoteTestCase("my_remote:folder", True, "underscore in name"),
}

TYPICAL_DATASETS = {
    "SIMPLE": RemoteTestCase("testpool/data", False, "simple dataset"),
    "NESTED": RemoteTestCase("tank/home/user", False, "nested dataset"),
    "SINGLE": RemoteTestCase("rpool", False, "single pool name"),
}

EDGE_CASES = {
    "ZFS_WITH_COLON": RemoteTestCase("tank/vm:disk0", False, "ZFS dataset with colon after slash"),
    "DEEP_NESTING": RemoteTestCase("pool/a/b/c/d", False, "deeply nested dataset"),
    "HYPHENATED": RemoteTestCase("my-pool/my-data", False, "hyphenated names"),
}


@dataclass(frozen=True)
class DirectionTestCase:
    """Test case for direction detection."""

    arg1: str
    arg2: str
    expected_direction: str  # "PUSH" or "PULL"
    expected_dataset: str
    expected_remote: str


DIRECTION_CASES = {
    "PUSH_SIMPLE": DirectionTestCase(
        "testpool/data", "dropbox:backup", "PUSH", "testpool/data", "dropbox:backup"
    ),
    "PULL_SIMPLE": DirectionTestCase(
        "dropbox:backup", "testpool/data", "PULL", "testpool/data", "dropbox:backup"
    ),
    "PUSH_NESTED": DirectionTestCase(
        "tank/home/user", "s3:bucket/prefix", "PUSH", "tank/home/user", "s3:bucket/prefix"
    ),
    "PULL_NESTED": DirectionTestCase(
        "remote:path/to/data", "rpool/docs", "PULL", "rpool/docs", "remote:path/to/data"
    ),
}


# =============================================================================
# Part 1: Remote Detection - FI3, FI4
# =============================================================================


class TestIsRcloneRemote:
    """Test is_rclone_remote function."""

    def test_dropbox_remote_detected(self) -> None:
        """FI4: dropbox:path is recognized as remote."""
        from cloud_mirror.direction import is_rclone_remote

        assert is_rclone_remote("dropbox:path") is True

    def test_remote_without_path_detected(self) -> None:
        """FI4: remote: (no path) is recognized as remote."""
        from cloud_mirror.direction import is_rclone_remote

        assert is_rclone_remote("remote:") is True

    def test_underscore_remote_detected(self) -> None:
        """FI4: my_remote:folder is recognized as remote."""
        from cloud_mirror.direction import is_rclone_remote

        assert is_rclone_remote("my_remote:folder") is True

    def test_s3_remote_detected(self) -> None:
        """FI4: s3:bucket/key is recognized as remote."""
        from cloud_mirror.direction import is_rclone_remote

        assert is_rclone_remote("s3:bucket/key") is True

    def test_simple_dataset_not_remote(self) -> None:
        """FI3: testpool/data is not a remote."""
        from cloud_mirror.direction import is_rclone_remote

        assert is_rclone_remote("testpool/data") is False

    def test_zfs_with_colon_not_remote(self) -> None:
        """FI3: tank/vm:disk0 is not remote (slash before colon)."""
        from cloud_mirror.direction import is_rclone_remote

        assert is_rclone_remote("tank/vm:disk0") is False

    def test_single_pool_not_remote(self) -> None:
        """Simple pool name without slash is not a remote."""
        from cloud_mirror.direction import is_rclone_remote

        assert is_rclone_remote("rpool") is False


class TestRemoteDetectionSystematic:
    """Systematic coverage of remote detection."""

    @pytest.mark.parametrize(
        ("name", "case"),
        list(TYPICAL_REMOTES.items()) + list(TYPICAL_DATASETS.items()) + list(EDGE_CASES.items()),
    )
    def test_all_cases(self, name: str, case: RemoteTestCase) -> None:
        """Test all remote detection cases."""
        from cloud_mirror.direction import is_rclone_remote

        result = is_rclone_remote(case.arg)
        assert result == case.is_remote, f"Failed for {name}: {case.reason}"


# =============================================================================
# Part 2: Direction Detection - FI1, FI2
# =============================================================================


class TestDetectDirection:
    """Test detect_direction function."""

    def test_push_detected_dataset_first(self) -> None:
        """FI1: dataset first, remote second -> PUSH."""
        from cloud_mirror.direction import SyncDirection, detect_direction

        result = detect_direction("testpool/data", "testremote:backup")

        assert result.direction == SyncDirection.PUSH
        assert result.zfs_dataset == "testpool/data"
        assert result.remote == "testremote:backup"

    def test_pull_detected_remote_first(self) -> None:
        """FI2: remote first, dataset second -> PULL."""
        from cloud_mirror.direction import SyncDirection, detect_direction

        result = detect_direction("testremote:backup", "testpool/data")

        assert result.direction == SyncDirection.PULL
        assert result.zfs_dataset == "testpool/data"
        assert result.remote == "testremote:backup"


class TestDirectionDetectionErrors:
    """Test error cases for direction detection."""

    def test_both_remotes_raises_error(self) -> None:
        """FI5: both arguments are remotes -> error."""
        from cloud_mirror.direction import DirectionError, detect_direction

        with pytest.raises(DirectionError) as exc_info:
            detect_direction("remote1:path", "remote2:path")

        assert "both" in str(exc_info.value).lower()
        assert "remote" in str(exc_info.value).lower()

    def test_neither_remote_raises_error(self) -> None:
        """FI6: neither argument is remote -> error."""
        from cloud_mirror.direction import DirectionError, detect_direction

        with pytest.raises(DirectionError) as exc_info:
            detect_direction("pool1/data", "pool2/backup")

        assert "neither" in str(exc_info.value).lower()


class TestDirectionDetectionSystematic:
    """Systematic coverage of direction detection."""

    @pytest.mark.parametrize(
        ("name", "case"),
        list(DIRECTION_CASES.items()),
    )
    def test_all_direction_cases(self, name: str, case: DirectionTestCase) -> None:
        """Test all direction detection cases."""
        from cloud_mirror.direction import SyncDirection, detect_direction

        result = detect_direction(case.arg1, case.arg2)

        expected_dir = SyncDirection.PUSH if case.expected_direction == "PUSH" else SyncDirection.PULL
        assert result.direction == expected_dir, f"Direction mismatch for {name}"
        assert result.zfs_dataset == case.expected_dataset, f"Dataset mismatch for {name}"
        assert result.remote == case.expected_remote, f"Remote mismatch for {name}"


# =============================================================================
# Part 3: Data Structures
# =============================================================================


class TestSyncDirection:
    """Test SyncDirection enum."""

    def test_push_exists(self) -> None:
        """SyncDirection.PUSH exists."""
        from cloud_mirror.direction import SyncDirection

        assert SyncDirection.PUSH is not None

    def test_pull_exists(self) -> None:
        """SyncDirection.PULL exists."""
        from cloud_mirror.direction import SyncDirection

        assert SyncDirection.PULL is not None


class TestSyncEndpoints:
    """Test SyncEndpoints dataclass."""

    def test_has_required_fields(self) -> None:
        """SyncEndpoints has direction, zfs_dataset, remote fields."""
        from cloud_mirror.direction import SyncDirection, SyncEndpoints

        endpoints = SyncEndpoints(
            direction=SyncDirection.PUSH,
            zfs_dataset="testpool/data",
            remote="dropbox:backup",
        )

        assert endpoints.direction == SyncDirection.PUSH
        assert endpoints.zfs_dataset == "testpool/data"
        assert endpoints.remote == "dropbox:backup"

    def test_is_frozen(self) -> None:
        """SyncEndpoints is immutable."""
        from cloud_mirror.direction import SyncDirection, SyncEndpoints

        endpoints = SyncEndpoints(
            direction=SyncDirection.PUSH,
            zfs_dataset="testpool/data",
            remote="dropbox:backup",
        )

        with pytest.raises(AttributeError):
            endpoints.direction = SyncDirection.PULL  # type: ignore[misc]
