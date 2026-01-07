"""Tests for git installation detection (FR1 of story-32)."""

from pathlib import Path

import pytest

from cloud_mirror.update import is_git_installation
from tests.fixtures.git_fixtures import with_git_repo


def test_detects_git_installation(tmp_path: Path) -> None:
    """Test that is_git_installation returns True for git repositories.

    GIVEN cloud-mirror is installed in a git repository
    WHEN is_git_installation() is called
    THEN it returns True
    """
    with with_git_repo(tmp_path) as repo:
        assert is_git_installation(repo.repo_path) is True


def test_detects_non_git_installation(tmp_path: Path) -> None:
    """Test that is_git_installation returns False for non-git directories.

    GIVEN cloud-mirror is installed by copying files (no .git directory)
    WHEN is_git_installation() is called
    THEN it returns False
    """
    # Create a directory without .git
    non_git_dir = tmp_path / "cloud_mirror"
    non_git_dir.mkdir()

    assert is_git_installation(non_git_dir) is False


def test_defaults_to_current_directory() -> None:
    """Test that is_git_installation uses current directory when path is None.

    Note: This test verifies the function signature, not behavior.
    In practice, we always pass explicit paths in tests.
    """
    # Just verify the function can be called without arguments
    # (it will return False since CWD is not a git repo during test)
    result = is_git_installation()
    assert isinstance(result, bool)
