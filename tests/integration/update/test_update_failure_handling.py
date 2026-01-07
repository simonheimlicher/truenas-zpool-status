"""Tests for update failure handling (FR3 of story-54)."""

import subprocess
from pathlib import Path

import pytest

from cloud_mirror.update import apply_update
from tests.fixtures.git_fixtures import with_git_repo


def test_apply_update_handles_network_failure(tmp_path: Path) -> None:
    """Test graceful handling when git pull fails due to network error.

    GIVEN git repository with invalid remote URL
    WHEN apply_update() is called
    THEN git pull fails
    AND returns UpdateResult(success=False, error=<message>)
    AND working directory remains at original commit
    """
    with with_git_repo(tmp_path, commits=["Initial"]) as repo:
        repo.create_tag("v0.1.0")
        original_commit = repo.current_commit()

        # Add invalid remote
        repo.run_git("remote", "add", "origin", "https://invalid.example.com/repo.git")

        # Try to update
        result = apply_update(repo.repo_path)

        assert result.success is False
        assert result.error is not None
        assert "failed" in result.error.lower() or "timeout" in result.error.lower()

        # Verify HEAD didn't move
        current_commit = repo.current_commit()
        assert current_commit == original_commit


def test_apply_update_handles_no_remote(tmp_path: Path) -> None:
    """Test handling when no remote is configured.

    GIVEN git repository with no remote
    WHEN apply_update() is called
    THEN returns UpdateResult(success=False)
    """
    with with_git_repo(tmp_path, commits=["Initial"]) as repo:
        repo.create_tag("v0.1.0")

        # No remote configured
        result = apply_update(repo.repo_path)

        assert result.success is False
        assert result.error is not None


def test_apply_update_atomic_on_failure(tmp_path: Path) -> None:
    """Test that failed update doesn't leave repository in broken state.

    GIVEN an update attempt that will fail
    WHEN apply_update() is called
    THEN repository state remains unchanged
    AND working directory is still functional
    """
    with with_git_repo(tmp_path, commits=["Initial", "Second"]) as repo:
        repo.create_tag("v0.1.0")
        original_commit = repo.current_commit()

        # Add invalid remote
        repo.run_git("remote", "add", "origin", "https://invalid.example.com/repo.git")

        # Try to update (will fail)
        result = apply_update(repo.repo_path)

        assert result.success is False

        # Verify repository is still functional
        # Can still make commits
        new_commit = repo.create_commit("After failed update", {"test.txt": "content"})
        assert new_commit != original_commit

        # git status should work
        status = repo.run_git("status", "--porcelain")
        assert status.returncode == 0
