"""Tests for version detection (FR2 of story-32)."""

from pathlib import Path

import pytest

from cloud_mirror.update import get_installed_version
from tests.fixtures.git_fixtures import with_git_repo


def test_get_version_from_tagged_commit(tmp_path: Path) -> None:
    """Test getting version from a tagged commit.

    GIVEN a git repository with a tagged commit (v0.1.0)
    WHEN get_installed_version() is called
    THEN it returns the tag name
    """
    with with_git_repo(tmp_path, commits=["Initial"]) as repo:
        repo.create_tag("v0.1.0")
        version = get_installed_version(repo.repo_path)
        assert version == "v0.1.0"


def test_get_version_with_commits_after_tag(tmp_path: Path) -> None:
    """Test getting version when commits exist after the tag.

    GIVEN a git repository with commits after the last tag
    WHEN get_installed_version() is called
    THEN it returns a version like "v0.1.0-3-gabcdef"
    """
    with with_git_repo(tmp_path, commits=["Initial"]) as repo:
        repo.create_tag("v0.1.0")

        # Add more commits after the tag
        repo.create_commit("Second", {"file2.txt": "content"})
        repo.create_commit("Third", {"file3.txt": "content"})

        version = get_installed_version(repo.repo_path)

        # Should be in format: v0.1.0-2-g<hash>
        assert version.startswith("v0.1.0-2-g")
        assert len(version.split("-")) == 3  # tag-count-hash


def test_get_version_no_tags(tmp_path: Path) -> None:
    """Test getting version when no tags exist.

    GIVEN a git repository with commits but no tags
    WHEN get_installed_version() is called
    THEN it returns a commit hash (git describe --always fallback)
    """
    with with_git_repo(tmp_path, commits=["Initial", "Second"]) as repo:
        version = get_installed_version(repo.repo_path)

        # Should return a commit hash
        assert len(version) == 7  # Short hash from --always
        assert all(c in "0123456789abcdef" for c in version)


def test_get_version_fallback_to_module_version(tmp_path: Path) -> None:
    """Test fallback to __version__ when git command fails.

    GIVEN a git repository where git describe fails
    WHEN get_installed_version() is called
    THEN it returns __version__ from cloud_mirror module
    """
    # Create a non-git directory
    non_git_dir = tmp_path / "not_git"
    non_git_dir.mkdir()

    version = get_installed_version(non_git_dir)

    # Should fall back to module __version__
    from cloud_mirror import __version__

    assert version == __version__


def test_get_version_defaults_to_current_directory() -> None:
    """Test that get_installed_version uses current directory when path is None."""
    # Should work without arguments (will use CWD)
    version = get_installed_version()
    assert isinstance(version, str)
    assert len(version) > 0
