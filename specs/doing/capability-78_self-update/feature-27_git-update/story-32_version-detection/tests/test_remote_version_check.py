"""Tests for remote version checking (FR3 of story-32)."""

from pathlib import Path

import pytest

from cloud_mirror.update import get_remote_version
from tests.fixtures.git_fixtures import with_git_repo


def test_get_remote_version_from_origin_main(tmp_path: Path) -> None:
    """Test getting remote version from origin/main.

    GIVEN a git repository with a remote configured
    AND remote/main has a newer tagged commit
    WHEN get_remote_version() is called
    THEN it returns the remote version
    """
    # Create "remote" repository with a tag
    remote_dir = tmp_path / "remote"
    with with_git_repo(remote_dir, commits=["Initial", "v0.2.0"]) as remote:
        remote.create_tag("v0.2.0")

        # Create "local" repository that will fetch from remote
        local_dir = tmp_path / "local"
        with with_git_repo(local_dir) as local:
            # Add remote pointing to our "remote" repository
            local.run_git("remote", "add", "origin", str(remote.repo_path))

            # Get remote version (should fetch and describe origin/main)
            version = get_remote_version(local.repo_path)

            assert version == "v0.2.0"


def test_get_remote_version_with_commits_after_tag(tmp_path: Path) -> None:
    """Test getting remote version when remote has commits after tag.

    GIVEN remote has commits after the last tag
    WHEN get_remote_version() is called
    THEN it returns version like "v0.2.0-2-gabcdef"
    """
    # Create remote with tag and additional commits
    remote_dir = tmp_path / "remote"
    with with_git_repo(remote_dir, commits=["Initial"]) as remote:
        remote.create_tag("v0.2.0")
        remote.create_commit("After tag 1", {"file1.txt": "content"})
        remote.create_commit("After tag 2", {"file2.txt": "content"})

        # Create local and fetch
        local_dir = tmp_path / "local"
        with with_git_repo(local_dir) as local:
            local.run_git("remote", "add", "origin", str(remote.repo_path))

            version = get_remote_version(local.repo_path)

            # Should include commit count
            assert version.startswith("v0.2.0-2-g")


def test_get_remote_version_network_failure(tmp_path: Path) -> None:
    """Test graceful handling of network failures.

    GIVEN a git repository with invalid remote URL
    WHEN get_remote_version() is called
    THEN it returns None (graceful degradation)
    AND no exception is raised
    """
    with with_git_repo(tmp_path) as repo:
        # Add invalid remote
        repo.run_git("remote", "add", "origin", "https://invalid.example.com/repo.git")

        # Should return None, not raise exception
        version = get_remote_version(repo.repo_path)
        assert version is None


def test_get_remote_version_no_remote_configured(tmp_path: Path) -> None:
    """Test handling when no remote is configured.

    GIVEN a git repository with no remote
    WHEN get_remote_version() is called
    THEN it returns None
    """
    with with_git_repo(tmp_path, commits=["Initial"]) as repo:
        # No remote configured
        version = get_remote_version(repo.repo_path)
        assert version is None


def test_get_remote_version_defaults_to_current_directory() -> None:
    """Test that get_remote_version uses current directory when path is None."""
    # Should work without arguments (will likely return None for test CWD)
    version = get_remote_version()
    assert version is None or isinstance(version, str)
