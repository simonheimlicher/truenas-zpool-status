"""
Level 2 Integration Tests: Basic File Sync with Local Backend.

Tests rclone sync operations using the local filesystem backend.
This validates rclone commands work without requiring internet access.

Run with: uv run --extra dev pytest tests/integration/rclone/test_basic_sync.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cloud_mirror.rclone import (
    RcloneSyncConfig,
    RcloneSyncError,
    SyncResult,
    run_rclone_sync,
)


# =============================================================================
# Test Values - Shared test data following 4-part debuggability pattern
# =============================================================================


class TestFiles:
    """Standard test file configurations."""

    SIMPLE = {
        "file1.txt": "content of file 1\n",
    }

    WITH_SUBDIRS = {
        "file1.txt": "content of file 1\n",
        "subdir/file2.txt": "content of file 2\n",
        "subdir/nested/file3.txt": "content of file 3\n",
    }

    WITH_SYMLINK = {
        "target.txt": "I am the target\n",
        # Symlink is created separately
    }

    EMPTY = {}


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


def create_files(base: Path, files: dict[str, str]) -> None:
    """Create files in a directory from a dict of path -> content."""
    for rel_path, content in files.items():
        file_path = base / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)


# =============================================================================
# Part 1: Typical Cases - Named tests for common scenarios
# =============================================================================


class TestTypicalSync:
    """GIVEN typical sync scenarios."""

    def test_simple_file_syncs(
        self,
        source_dir: Path,
        dest_dir: Path,
        rclone_config_path: Path,
        rclone_bin: str,
    ) -> None:
        """WHEN syncing a single file THEN file appears in destination."""
        # Arrange
        create_files(source_dir, TestFiles.SIMPLE)
        config = RcloneSyncConfig(
            source=source_dir,
            destination=f"testremote:{dest_dir}",
            config_path=rclone_config_path,
        )

        # Act
        result = run_rclone_sync(config, rclone_bin=rclone_bin)

        # Assert
        assert result.success
        assert (dest_dir / "file1.txt").exists()
        assert (dest_dir / "file1.txt").read_text() == "content of file 1\n"

    def test_directory_structure_preserved(
        self,
        source_dir: Path,
        dest_dir: Path,
        rclone_config_path: Path,
        rclone_bin: str,
    ) -> None:
        """WHEN syncing nested directories THEN structure is preserved."""
        # Arrange
        create_files(source_dir, TestFiles.WITH_SUBDIRS)
        config = RcloneSyncConfig(
            source=source_dir,
            destination=f"testremote:{dest_dir}",
            config_path=rclone_config_path,
        )

        # Act
        result = run_rclone_sync(config, rclone_bin=rclone_bin)

        # Assert
        assert result.success
        assert (dest_dir / "file1.txt").exists()
        assert (dest_dir / "subdir" / "file2.txt").exists()
        assert (dest_dir / "subdir" / "nested" / "file3.txt").exists()

    def test_symlink_handled_with_links_flag(
        self,
        source_dir: Path,
        dest_dir: Path,
        rclone_config_path: Path,
        rclone_bin: str,
    ) -> None:
        """WHEN syncing symlinks with --links THEN symlinks are preserved.

        Note: With local backend, symlinks are preserved as symlinks.
        With cloud backends (Level 3), they become .rclonelink files.
        """
        # Arrange
        create_files(source_dir, TestFiles.WITH_SYMLINK)
        symlink = source_dir / "link.txt"
        symlink.symlink_to("target.txt")

        config = RcloneSyncConfig(
            source=source_dir,
            destination=f"testremote:{dest_dir}",
            config_path=rclone_config_path,
        )

        # Act
        result = run_rclone_sync(config, rclone_bin=rclone_bin)

        # Assert
        assert result.success
        assert (dest_dir / "target.txt").exists()
        # With local backend, symlink is preserved as symlink
        link_path = dest_dir / "link.txt"
        assert link_path.is_symlink(), f"Expected {link_path} to be a symlink"
        assert link_path.resolve().name == "target.txt"


# =============================================================================
# Part 2: Edge Cases - Named tests for boundary conditions
# =============================================================================


class TestEdgeCases:
    """GIVEN edge case scenarios."""

    def test_empty_source_syncs_successfully(
        self,
        source_dir: Path,
        dest_dir: Path,
        rclone_config_path: Path,
        rclone_bin: str,
    ) -> None:
        """WHEN source is empty THEN sync succeeds with no files."""
        # Arrange - source_dir is already empty
        config = RcloneSyncConfig(
            source=source_dir,
            destination=f"testremote:{dest_dir}",
            config_path=rclone_config_path,
        )

        # Act
        result = run_rclone_sync(config, rclone_bin=rclone_bin)

        # Assert
        assert result.success
        assert result.files_transferred == 0

    def test_dry_run_does_not_transfer(
        self,
        source_dir: Path,
        dest_dir: Path,
        rclone_config_path: Path,
        rclone_bin: str,
    ) -> None:
        """WHEN dry_run=True THEN no files are actually transferred."""
        # Arrange
        create_files(source_dir, TestFiles.SIMPLE)
        config = RcloneSyncConfig(
            source=source_dir,
            destination=f"testremote:{dest_dir}",
            config_path=rclone_config_path,
            dry_run=True,
        )

        # Act
        result = run_rclone_sync(config, rclone_bin=rclone_bin)

        # Assert
        assert result.success
        assert not (dest_dir / "file1.txt").exists()

    def test_idempotent_sync_no_changes(
        self,
        source_dir: Path,
        dest_dir: Path,
        rclone_config_path: Path,
        rclone_bin: str,
    ) -> None:
        """WHEN syncing twice THEN second sync transfers nothing."""
        # Arrange
        create_files(source_dir, TestFiles.SIMPLE)
        config = RcloneSyncConfig(
            source=source_dir,
            destination=f"testremote:{dest_dir}",
            config_path=rclone_config_path,
        )

        # Act - first sync
        result1 = run_rclone_sync(config, rclone_bin=rclone_bin)
        # Act - second sync (should be no-op)
        result2 = run_rclone_sync(config, rclone_bin=rclone_bin)

        # Assert
        assert result1.success
        assert result2.success
        # Second sync should transfer 0 files (checksum match)
        assert result2.files_transferred == 0


# =============================================================================
# Part 3: Error Handling - Tests for failure scenarios
# =============================================================================


class TestErrorHandling:
    """GIVEN error scenarios."""

    def test_invalid_remote_raises_error(
        self,
        source_dir: Path,
        rclone_config_path: Path,
        rclone_bin: str,
    ) -> None:
        """WHEN remote is invalid THEN raises RcloneSyncError."""
        # Arrange
        create_files(source_dir, TestFiles.SIMPLE)
        config = RcloneSyncConfig(
            source=source_dir,
            destination="nonexistent-remote:path",
            config_path=rclone_config_path,
        )

        # Act & Assert
        with pytest.raises(RcloneSyncError) as exc_info:
            run_rclone_sync(config, rclone_bin=rclone_bin)

        assert exc_info.value.returncode != 0
        assert "Suggestion:" in str(exc_info.value)

    def test_missing_rclone_binary_raises_error(
        self,
        source_dir: Path,
        dest_dir: Path,
        rclone_config_path: Path,
    ) -> None:
        """WHEN rclone binary not found THEN raises RcloneSyncError."""
        # Arrange
        create_files(source_dir, TestFiles.SIMPLE)
        config = RcloneSyncConfig(
            source=source_dir,
            destination=f"testremote:{dest_dir}",
            config_path=rclone_config_path,
        )

        # Act & Assert
        with pytest.raises(RcloneSyncError) as exc_info:
            run_rclone_sync(config, rclone_bin="/nonexistent/rclone")

        assert "not found" in str(exc_info.value)
        assert "Install rclone" in exc_info.value.suggestion


# =============================================================================
# Part 4: SyncResult Verification - Tests for result object
# =============================================================================


class TestSyncResult:
    """GIVEN sync results."""

    def test_result_contains_stdout(
        self,
        source_dir: Path,
        dest_dir: Path,
        rclone_config_path: Path,
        rclone_bin: str,
    ) -> None:
        """WHEN sync completes THEN result contains stdout."""
        # Arrange
        create_files(source_dir, TestFiles.SIMPLE)
        config = RcloneSyncConfig(
            source=source_dir,
            destination=f"testremote:{dest_dir}",
            config_path=rclone_config_path,
        )

        # Act
        result = run_rclone_sync(config, rclone_bin=rclone_bin)

        # Assert
        assert result.success
        assert isinstance(result.stdout, str)
        assert result.returncode == 0

    def test_result_is_frozen_dataclass(
        self,
        source_dir: Path,
        dest_dir: Path,
        rclone_config_path: Path,
        rclone_bin: str,
    ) -> None:
        """WHEN result returned THEN it is immutable."""
        # Arrange
        create_files(source_dir, TestFiles.SIMPLE)
        config = RcloneSyncConfig(
            source=source_dir,
            destination=f"testremote:{dest_dir}",
            config_path=rclone_config_path,
        )

        # Act
        result = run_rclone_sync(config, rclone_bin=rclone_bin)

        # Assert - frozen dataclass cannot be modified
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]
