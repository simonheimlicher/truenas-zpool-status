"""
Level 3 Integration Tests: Real Dropbox Sync.

MANDATORY tests per ADR-001. These tests verify that sync operations
work correctly with real Dropbox, including authentication, rate limiting,
and Dropbox-specific behaviors.

These tests require:
- DROPBOX_TEST_TOKEN environment variable (or in .env file)
- Internet connectivity
- Dropbox test account with cloud-mirror-test folder

Run with: uv run --extra dev pytest tests/integration/rclone/test_dropbox_sync.py -v -m internet_required
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cloud_mirror.rclone import (
    RcloneSyncConfig,
    RcloneSyncError,
    cleanup_old_versions,
    get_versions_base_path,
    run_rclone_sync,
    VERSIONS_DIR,
)


def _run_rclone_verify(
    rclone_bin: str, cmd: str, remote: str, config: Path, timeout: int = 30
) -> subprocess.CompletedProcess[str]:
    """Run rclone command for verification (test helper).

    This is a test utility, not production code. Commands are built from
    trusted test fixtures, not user input.
    """
    return subprocess.run(  # noqa: S603 - test helper with controlled inputs
        [rclone_bin, cmd, remote, "--config", str(config)],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# =============================================================================
# Test Values - Shared test data
# =============================================================================


class TestFiles:
    """Standard test file configurations for Dropbox tests."""

    SIMPLE = {
        "file1.txt": "content of file 1\n",
    }

    WITH_SUBDIRS = {
        "file1.txt": "content of file 1\n",
        "subdir/file2.txt": "content of file 2\n",
    }

    WITH_SYMLINK = {
        "target.txt": "I am the target\n",
        # Symlink is created separately
    }

    # For rate limit testing - 50 small files
    MANY_FILES = {f"file_{i:03d}.txt": f"content {i}\n" for i in range(50)}


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
# Part 1: Typical Cases - Real Dropbox sync
# =============================================================================


@pytest.mark.internet_required
class TestDropboxSync:
    """GIVEN real Dropbox remote. MANDATORY Level 3 tests per ADR-001."""

    def test_files_sync_to_dropbox(
        self,
        source_dir: Path,
        dropbox_test_folder: str,
        dropbox_config: Path,
        rclone_bin: str,
    ) -> None:
        """FR1 at Level 3: Verify files actually appear on Dropbox."""
        # Arrange
        create_files(source_dir, TestFiles.SIMPLE)
        config = RcloneSyncConfig(
            source=source_dir,
            destination=dropbox_test_folder,
            config_path=dropbox_config,
            tpslimit=8,  # Be gentle with Dropbox API
        )

        # Act
        result = run_rclone_sync(config, rclone_bin=rclone_bin, timeout=120)

        # Assert
        assert result.success
        assert result.returncode == 0

        # Verify file actually exists on Dropbox
        verify = _run_rclone_verify(rclone_bin, "ls", dropbox_test_folder, dropbox_config)
        assert "file1.txt" in verify.stdout

    def test_directory_structure_preserved_on_dropbox(
        self,
        source_dir: Path,
        dropbox_test_folder: str,
        dropbox_config: Path,
        rclone_bin: str,
    ) -> None:
        """FR1 at Level 3: Verify directory structure on Dropbox."""
        # Arrange
        create_files(source_dir, TestFiles.WITH_SUBDIRS)
        config = RcloneSyncConfig(
            source=source_dir,
            destination=dropbox_test_folder,
            config_path=dropbox_config,
            tpslimit=8,
        )

        # Act
        result = run_rclone_sync(config, rclone_bin=rclone_bin, timeout=120)

        # Assert
        assert result.success

        # Verify structure on Dropbox
        verify = _run_rclone_verify(rclone_bin, "ls", dropbox_test_folder, dropbox_config)
        assert "file1.txt" in verify.stdout
        assert "subdir/file2.txt" in verify.stdout

    def test_symlinks_become_rclonelink_on_dropbox(
        self,
        source_dir: Path,
        dropbox_test_folder: str,
        dropbox_config: Path,
        rclone_bin: str,
    ) -> None:
        """FR2 at Level 3: Verify .rclonelink works on Dropbox."""
        # Arrange
        create_files(source_dir, TestFiles.WITH_SYMLINK)
        symlink = source_dir / "link.txt"
        symlink.symlink_to("target.txt")

        config = RcloneSyncConfig(
            source=source_dir,
            destination=dropbox_test_folder,
            config_path=dropbox_config,
            tpslimit=8,
        )

        # Act
        result = run_rclone_sync(config, rclone_bin=rclone_bin, timeout=120)

        # Assert
        assert result.success

        # Verify .rclonelink file on Dropbox
        verify = _run_rclone_verify(rclone_bin, "ls", dropbox_test_folder, dropbox_config)
        assert "target.txt" in verify.stdout
        assert "link.txt.rclonelink" in verify.stdout


# =============================================================================
# Part 2: Rate Limit Handling
# =============================================================================


@pytest.mark.internet_required
class TestDropboxRateLimits:
    """GIVEN Dropbox rate limit scenarios. Tests per ADR-001."""

    @pytest.mark.flaky(reruns=3)  # Transient failures expected
    def test_tpslimit_prevents_rate_errors(
        self,
        source_dir: Path,
        dropbox_test_folder: str,
        dropbox_config: Path,
        rclone_bin: str,
    ) -> None:
        """Sync 50 files with tpslimit=8, verify no rate limit errors."""
        # Arrange
        create_files(source_dir, TestFiles.MANY_FILES)
        config = RcloneSyncConfig(
            source=source_dir,
            destination=dropbox_test_folder,
            config_path=dropbox_config,
            tpslimit=8,  # Conservative rate limit
            transfers=4,  # Fewer parallel transfers
        )

        # Act
        result = run_rclone_sync(config, rclone_bin=rclone_bin, timeout=300)

        # Assert
        assert result.success
        # Check no rate limit errors in parsed errors
        rate_limit_errors = [e for e in result.errors if e.category == "rate_limit"]
        assert len(rate_limit_errors) == 0, f"Rate limit errors: {rate_limit_errors}"


# =============================================================================
# Part 3: Authentication Handling
# =============================================================================


@pytest.mark.internet_required
class TestDropboxAuth:
    """GIVEN Dropbox authentication scenarios."""

    def test_valid_token_authenticates(
        self,
        dropbox_config: Path,
        rclone_bin: str,
    ) -> None:
        """Verify test account credentials work."""
        # Just try to list the remote root
        result = _run_rclone_verify(rclone_bin, "lsd", "dropbox-test:", dropbox_config)
        assert result.returncode == 0, f"Auth failed: {result.stderr}"

    def test_invalid_token_reports_helpful_error(
        self,
        source_dir: Path,
        tmp_path: Path,
        rclone_bin: str,
    ) -> None:
        """When token is invalid, error suggests 'rclone config reconnect'."""
        # Arrange - create config with invalid token
        bad_config = tmp_path / "bad-rclone.conf"
        bad_config.write_text("""[dropbox-test]
type = dropbox
token = {"access_token":"INVALID_TOKEN","token_type":"bearer","expiry":"2020-01-01T00:00:00Z"}
""")
        create_files(source_dir, TestFiles.SIMPLE)

        config = RcloneSyncConfig(
            source=source_dir,
            destination="dropbox-test:test",
            config_path=bad_config,
        )

        # Act & Assert
        with pytest.raises(RcloneSyncError) as exc_info:
            run_rclone_sync(config, rclone_bin=rclone_bin, timeout=30)

        # Should have auth-related error
        error_str = str(exc_info.value)
        suggestion = exc_info.value.suggestion
        # Either the error or suggestion should guide the user
        assert (
            "token" in error_str.lower()
            or "auth" in error_str.lower()
            or "reconnect" in suggestion.lower()
            or "credentials" in suggestion.lower()
        ), f"Error should mention auth issue: {error_str}, suggestion: {suggestion}"


# =============================================================================
# Part 4: Idempotency on Real Dropbox
# =============================================================================


@pytest.mark.internet_required
class TestDropboxIdempotency:
    """GIVEN idempotent sync requirements."""

    def test_second_sync_transfers_nothing(
        self,
        source_dir: Path,
        dropbox_test_folder: str,
        dropbox_config: Path,
        rclone_bin: str,
    ) -> None:
        """When syncing twice, second sync should transfer 0 files."""
        # Arrange
        create_files(source_dir, TestFiles.SIMPLE)
        config = RcloneSyncConfig(
            source=source_dir,
            destination=dropbox_test_folder,
            config_path=dropbox_config,
            tpslimit=8,
        )

        # Act - first sync
        result1 = run_rclone_sync(config, rclone_bin=rclone_bin, timeout=120)
        # Act - second sync (should be no-op with --checksum)
        result2 = run_rclone_sync(config, rclone_bin=rclone_bin, timeout=120)

        # Assert
        assert result1.success
        assert result2.success
        # Second sync should transfer 0 files because checksums match
        assert (
            result2.files_transferred == 0
        ), f"Expected 0 files, got {result2.files_transferred}"


# =============================================================================
# Part 5: Version Backup on Real Dropbox (FR1, FR2, FR3)
# =============================================================================


def _run_rclone_mkdir(
    rclone_bin: str, remote: str, config: Path, timeout: int = 30
) -> subprocess.CompletedProcess[str]:
    """Create directory on remote."""
    return subprocess.run(  # noqa: S603 - test helper with controlled inputs
        [rclone_bin, "mkdir", remote, "--config", str(config)],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _run_rclone_copy(
    rclone_bin: str, source: str, dest: str, config: Path, timeout: int = 30
) -> subprocess.CompletedProcess[str]:
    """Copy file to remote."""
    return subprocess.run(  # noqa: S603 - test helper with controlled inputs
        [rclone_bin, "copy", source, dest, "--config", str(config)],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@pytest.mark.internet_required
class TestDropboxVersionBackup:
    """GIVEN real Dropbox version backup. Level 3 tests per ADR-001."""

    def test_version_backup_works_on_dropbox(
        self,
        source_dir: Path,
        dropbox_test_folder: str,
        dropbox_config: Path,
        rclone_bin: str,
    ) -> None:
        """FR1/FR2 at Level 3: Verify --backup-dir works with Dropbox."""
        # Arrange - create initial file on Dropbox
        initial_file = source_dir / "initial.txt"
        initial_file.write_text("initial content\n")

        # First sync to establish the file
        config1 = RcloneSyncConfig(
            source=source_dir,
            destination=dropbox_test_folder,
            config_path=dropbox_config,
            tpslimit=8,
        )
        result1 = run_rclone_sync(config1, rclone_bin=rclone_bin, timeout=120)
        assert result1.success

        # Modify the file
        initial_file.write_text("modified content\n")

        # Second sync with versioning
        timestamp = "2025-01-15T12-00-00Z"
        config2 = RcloneSyncConfig(
            source=source_dir,
            destination=dropbox_test_folder,
            config_path=dropbox_config,
            keep_versions=3,
            timestamp=timestamp,
            tpslimit=8,
        )
        result2 = run_rclone_sync(config2, rclone_bin=rclone_bin, timeout=120)

        # Assert
        assert result2.success

        # Verify backup exists on Dropbox (sibling path structure)
        backup_path = f"{get_versions_base_path(dropbox_test_folder)}/{timestamp}"
        verify = _run_rclone_verify(rclone_bin, "ls", backup_path, dropbox_config)
        assert "initial.txt" in verify.stdout, f"Backup not found: {verify.stdout}"

    def test_cleanup_works_on_dropbox(
        self,
        dropbox_test_folder: str,
        dropbox_config: Path,
        rclone_bin: str,
    ) -> None:
        """FR3 at Level 3: Verify cleanup_old_versions works with Dropbox."""
        # Arrange - create 4 version directories on Dropbox (sibling path structure)
        timestamps = [
            "2025-01-10T00-00-00Z",
            "2025-01-11T00-00-00Z",
            "2025-01-12T00-00-00Z",
            "2025-01-13T00-00-00Z",
        ]

        versions_base = get_versions_base_path(dropbox_test_folder)
        for ts in timestamps:
            version_path = f"{versions_base}/{ts}"
            _run_rclone_mkdir(rclone_bin, version_path, dropbox_config)

        # Act - cleanup, keep only 2
        result = cleanup_old_versions(
            destination=dropbox_test_folder,
            config_path=dropbox_config,
            keep_versions=2,
            rclone_bin=rclone_bin,
            timeout=120,
        )

        # Assert
        assert result.success
        assert result.deleted_count == 2
        assert result.remaining_count == 2

        # Verify only newest 2 remain (sibling path structure)
        verify = _run_rclone_verify(rclone_bin, "lsd", versions_base, dropbox_config)
        assert "2025-01-10T00-00-00Z" not in verify.stdout
        assert "2025-01-11T00-00-00Z" not in verify.stdout
        assert "2025-01-12T00-00-00Z" in verify.stdout
        assert "2025-01-13T00-00-00Z" in verify.stdout
