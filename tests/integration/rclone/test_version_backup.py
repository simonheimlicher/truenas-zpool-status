"""
Level 2 Integration Tests: Version Backup with Local Backend.

Tests version backup and cleanup operations using the local filesystem backend.
This validates rclone --backup-dir and cleanup logic without requiring internet.

Run with: uv run --extra dev pytest tests/integration/rclone/test_version_backup.py -v
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cloud_mirror.rclone import (
    CleanupResult,
    RcloneSyncConfig,
    cleanup_old_versions,
    list_version_directories,
    run_rclone_sync,
    VERSIONS_DIR,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    """Create a source directory for sync tests."""
    source = tmp_path / "source"
    source.mkdir()
    return source


@pytest.fixture
def dest_dir(tmp_path: Path) -> Path:
    """Create a destination directory for sync tests."""
    dest = tmp_path / "dest"
    dest.mkdir()
    return dest


@pytest.fixture
def rclone_config_path() -> Path:
    """Get path to test rclone configuration."""
    config_path = Path(__file__).parent.parent.parent / "rclone-test.conf"
    if not config_path.exists():
        pytest.skip("rclone-test.conf not found")
    return config_path


@pytest.fixture
def rclone_bin() -> str:
    """Get path to rclone binary."""
    import shutil

    rclone = shutil.which("rclone")
    if not rclone:
        pytest.skip("rclone not installed")
    return rclone


def create_file(path: Path, content: str) -> None:
    """Create a file with content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def create_version_dirs(dest: Path, timestamps: list[str]) -> Path:
    """Create version directories at sibling location for testing cleanup.

    The .versions directory is placed as a sibling to the destination,
    not inside it. This matches the production path structure.

    For dest=/tmp/xyz/dest, versions are at /tmp/xyz/.versions/dest/

    Returns the versions base directory for verification.
    """
    # Sibling structure: parent/.versions/dest_name/
    versions_base = dest.parent / VERSIONS_DIR / dest.name
    versions_base.mkdir(parents=True, exist_ok=True)
    for ts in timestamps:
        version_dir = versions_base / ts
        version_dir.mkdir()
        # Add a dummy file to make it a non-empty directory
        (version_dir / "dummy.txt").write_text("version content")
    return versions_base


# =============================================================================
# Part 1: Version Backup Tests (FR1, FR2)
# =============================================================================


class TestVersionBackup:
    """GIVEN version backup scenarios.

    Note: For local backend, rclone requires --backup-dir to be outside
    the destination directory (they can't overlap). Full FR1/FR2 testing
    happens at Level 3 with real Dropbox where this works correctly.
    Here we verify command building and basic behavior.
    """

    def test_backup_dir_in_command_when_versioning_enabled(
        self,
        source_dir: Path,
        rclone_config_path: Path,
    ) -> None:
        """FR1/FR2: WHEN versioning enabled THEN --backup-dir included in command."""
        from cloud_mirror.rclone import build_rclone_command

        # Arrange
        timestamp = "2025-01-15T12-00-00Z"
        config = RcloneSyncConfig(
            source=source_dir,
            destination="dropbox:backup",  # Cloud destination
            config_path=rclone_config_path,
            keep_versions=3,
            timestamp=timestamp,
        )

        # Act
        cmd = build_rclone_command(config)

        # Assert
        assert "--backup-dir" in cmd
        backup_dir_idx = cmd.index("--backup-dir")
        backup_path = cmd[backup_dir_idx + 1]
        assert ".versions" in backup_path
        assert timestamp in backup_path

    def test_no_backup_dir_without_timestamp(
        self,
        source_dir: Path,
        rclone_config_path: Path,
    ) -> None:
        """WHEN keep_versions > 0 but no timestamp THEN no --backup-dir."""
        from cloud_mirror.rclone import build_rclone_command

        # Arrange - missing timestamp
        config = RcloneSyncConfig(
            source=source_dir,
            destination="dropbox:backup",
            config_path=rclone_config_path,
            keep_versions=3,
            timestamp="",  # No timestamp
        )

        # Act
        cmd = build_rclone_command(config)

        # Assert
        assert "--backup-dir" not in cmd

    def test_no_backup_when_versions_disabled(
        self,
        source_dir: Path,
        dest_dir: Path,
        rclone_config_path: Path,
        rclone_bin: str,
    ) -> None:
        """WHEN keep_versions=0 THEN no backup directory created."""
        # Arrange
        create_file(dest_dir / "file1.txt", "old content")
        create_file(source_dir / "file1.txt", "new content")

        config = RcloneSyncConfig(
            source=source_dir,
            destination=f"testremote:{dest_dir}",
            config_path=rclone_config_path,
            keep_versions=0,  # Disabled
        )

        # Act
        result = run_rclone_sync(config, rclone_bin=rclone_bin)

        # Assert
        assert result.success
        assert (dest_dir / "file1.txt").read_text() == "new content"
        # No versions directory created
        assert not (dest_dir / VERSIONS_DIR).exists()


# =============================================================================
# Part 2: Version Cleanup Tests (FR3, FR4)
# =============================================================================


class TestVersionCleanup:
    """GIVEN version cleanup scenarios."""

    def test_cleanup_deletes_oldest_versions(
        self,
        dest_dir: Path,
        rclone_config_path: Path,
        rclone_bin: str,
    ) -> None:
        """FR3: WHEN 5 versions exist and keep_versions=3 THEN 2 oldest deleted."""
        # Arrange - create 5 version directories
        timestamps = [
            "2025-01-10T00-00-00Z",
            "2025-01-11T00-00-00Z",
            "2025-01-12T00-00-00Z",
            "2025-01-13T00-00-00Z",
            "2025-01-14T00-00-00Z",
        ]
        versions_base = create_version_dirs(dest_dir, timestamps)

        # Act
        result = cleanup_old_versions(
            destination=f"testremote:{dest_dir}",
            config_path=rclone_config_path,
            keep_versions=3,
            rclone_bin=rclone_bin,
        )

        # Assert
        assert result.success
        assert result.deleted_count == 2
        assert result.remaining_count == 3

        # Oldest 2 should be deleted (sibling location)
        assert not (versions_base / "2025-01-10T00-00-00Z").exists()
        assert not (versions_base / "2025-01-11T00-00-00Z").exists()

        # Newest 3 should remain
        assert (versions_base / "2025-01-12T00-00-00Z").exists()
        assert (versions_base / "2025-01-13T00-00-00Z").exists()
        assert (versions_base / "2025-01-14T00-00-00Z").exists()

    def test_cleanup_skips_when_not_enough_versions(
        self,
        dest_dir: Path,
        rclone_config_path: Path,
        rclone_bin: str,
    ) -> None:
        """FR4: WHEN only 2 versions exist and keep_versions=3 THEN no deletion."""
        # Arrange - create only 2 version directories
        timestamps = [
            "2025-01-10T00-00-00Z",
            "2025-01-11T00-00-00Z",
        ]
        versions_base = create_version_dirs(dest_dir, timestamps)

        # Act
        result = cleanup_old_versions(
            destination=f"testremote:{dest_dir}",
            config_path=rclone_config_path,
            keep_versions=3,
            rclone_bin=rclone_bin,
        )

        # Assert
        assert result.success
        assert result.deleted_count == 0
        assert result.remaining_count == 2

        # Both should still exist (sibling location)
        assert (versions_base / "2025-01-10T00-00-00Z").exists()
        assert (versions_base / "2025-01-11T00-00-00Z").exists()

    def test_cleanup_handles_no_versions_directory(
        self,
        dest_dir: Path,
        rclone_config_path: Path,
        rclone_bin: str,
    ) -> None:
        """WHEN .versions/ doesn't exist THEN returns success with 0 deleted."""
        # Act - no versions directory exists
        result = cleanup_old_versions(
            destination=f"testremote:{dest_dir}",
            config_path=rclone_config_path,
            keep_versions=3,
            rclone_bin=rclone_bin,
        )

        # Assert
        assert result.success
        assert result.deleted_count == 0
        assert result.remaining_count == 0


# =============================================================================
# Part 3: List Version Directories Tests
# =============================================================================


class TestListVersionDirectories:
    """GIVEN version directory listing scenarios."""

    def test_lists_versions_sorted_oldest_first(
        self,
        dest_dir: Path,
        rclone_config_path: Path,
        rclone_bin: str,
    ) -> None:
        """WHEN versions exist THEN returns sorted list oldest first."""
        # Arrange - create directories in random order
        timestamps = [
            "2025-01-14T00-00-00Z",
            "2025-01-10T00-00-00Z",
            "2025-01-12T00-00-00Z",
        ]
        create_version_dirs(dest_dir, timestamps)

        # Act
        versions = list_version_directories(
            destination=f"testremote:{dest_dir}",
            config_path=rclone_config_path,
            rclone_bin=rclone_bin,
        )

        # Assert
        assert versions == [
            "2025-01-10T00-00-00Z",
            "2025-01-12T00-00-00Z",
            "2025-01-14T00-00-00Z",
        ]

    def test_returns_empty_list_when_no_versions(
        self,
        dest_dir: Path,
        rclone_config_path: Path,
        rclone_bin: str,
    ) -> None:
        """WHEN .versions/ doesn't exist THEN returns empty list."""
        # Act
        versions = list_version_directories(
            destination=f"testremote:{dest_dir}",
            config_path=rclone_config_path,
            rclone_bin=rclone_bin,
        )

        # Assert
        assert versions == []


# =============================================================================
# Part 4: CleanupResult Dataclass Tests
# =============================================================================


class TestCleanupResult:
    """GIVEN CleanupResult dataclass."""

    def test_cleanup_result_is_frozen(self) -> None:
        """WHEN creating CleanupResult THEN it is immutable."""
        result = CleanupResult(success=True)

        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]

    def test_cleanup_result_defaults(self) -> None:
        """WHEN creating CleanupResult with only success THEN defaults applied."""
        result = CleanupResult(success=True)

        assert result.success
        assert result.deleted_count == 0
        assert result.remaining_count == 0
        assert result.deleted_versions == []
        assert result.errors == []
