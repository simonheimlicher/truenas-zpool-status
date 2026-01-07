"""Tests for dirty working directory detection (FR1 of story-54)."""

from pathlib import Path

import pytest

from cloud_mirror.update import UpdateResult, apply_update, has_uncommitted_changes
from tests.fixtures.git_fixtures import with_git_repo


def test_has_uncommitted_changes_detects_modified_files(tmp_path: Path) -> None:
    """Test detection of modified files.

    GIVEN a git repository with a modified file
    WHEN has_uncommitted_changes() is called
    THEN it returns True
    """
    with with_git_repo(tmp_path, commits=["Initial"]) as repo:
        repo.create_commit("Add file", {"tracked.txt": "original"})

        # Modify the file
        (repo.repo_path / "tracked.txt").write_text("modified")

        assert has_uncommitted_changes(repo.repo_path) is True


def test_has_uncommitted_changes_detects_new_files(tmp_path: Path) -> None:
    """Test detection of untracked files.

    GIVEN a git repository with a new untracked file
    WHEN has_uncommitted_changes() is called
    THEN it returns True
    """
    with with_git_repo(tmp_path, commits=["Initial"]) as repo:
        # Create untracked file
        (repo.repo_path / "new_file.txt").write_text("new content")

        assert has_uncommitted_changes(repo.repo_path) is True


def test_has_uncommitted_changes_detects_staged_files(tmp_path: Path) -> None:
    """Test detection of staged but uncommitted files.

    GIVEN a git repository with staged changes
    WHEN has_uncommitted_changes() is called
    THEN it returns True
    """
    with with_git_repo(tmp_path, commits=["Initial"]) as repo:
        # Create and stage a file
        (repo.repo_path / "staged.txt").write_text("staged content")
        repo.run_git("add", "staged.txt")

        assert has_uncommitted_changes(repo.repo_path) is True


def test_has_uncommitted_changes_clean_repo(tmp_path: Path) -> None:
    """Test that clean repository returns False.

    GIVEN a clean git repository (no uncommitted changes)
    WHEN has_uncommitted_changes() is called
    THEN it returns False
    """
    with with_git_repo(tmp_path, commits=["Initial"]) as repo:
        assert has_uncommitted_changes(repo.repo_path) is False


def test_apply_update_aborts_with_uncommitted_changes(tmp_path: Path) -> None:
    """Test that apply_update aborts when working directory is dirty.

    GIVEN a git repository with uncommitted changes
    AND an update is available
    WHEN apply_update() is called
    THEN update is aborted before git pull
    AND returns UpdateResult(success=False, error="Uncommitted changes detected")
    AND working directory remains unchanged
    """
    # Create remote with update
    remote_dir = tmp_path / "remote"
    with with_git_repo(remote_dir, commits=["Initial"]) as remote:
        remote.create_tag("v0.1.0")
        remote.create_commit("Update", {"updated.txt": "new"})

        # Clone to local
        local_dir = tmp_path / "local"
        local_dir.mkdir()
        import subprocess

        subprocess.run(
            ["git", "clone", str(remote.repo_path), str(local_dir)],
            capture_output=True,
            check=True,
        )

        # Reset local to v0.1.0
        subprocess.run(
            ["git", "-C", str(local_dir), "reset", "--hard", "v0.1.0"],
            capture_output=True,
            check=True,
        )

        original_commit = subprocess.run(
            ["git", "-C", str(local_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        # Make uncommitted changes
        (local_dir / "dirty.txt").write_text("uncommitted")

        # Try to apply update
        result = apply_update(local_dir)

        assert result.success is False
        assert result.error is not None
        assert "uncommitted" in result.error.lower() or "dirty" in result.error.lower()

        # Verify HEAD didn't move
        current_commit = subprocess.run(
            ["git", "-C", str(local_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        assert current_commit == original_commit
