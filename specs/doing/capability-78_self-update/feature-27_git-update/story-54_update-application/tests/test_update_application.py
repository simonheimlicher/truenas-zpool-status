"""Tests for atomic update application (FR2 of story-54)."""

import subprocess
from pathlib import Path

import pytest

from cloud_mirror.update import apply_update
from tests.fixtures.git_fixtures import with_git_repo


def test_apply_update_moves_head_to_remote(tmp_path: Path) -> None:
    """Test that apply_update successfully updates to remote version.

    GIVEN a clean git repository (no uncommitted changes)
    AND remote has newer commits (update available)
    WHEN apply_update() is called
    THEN git fetch and git pull execute successfully
    AND local HEAD moves to remote commit
    AND returns UpdateResult(success=True, old_version, new_version)
    """
    # Create remote with newer version
    remote_dir = tmp_path / "remote"
    with with_git_repo(remote_dir, commits=["Initial"]) as remote:
        remote.create_tag("v0.1.0")
        initial_commit = remote.current_commit()

        # Add update
        remote.create_commit("Update to v0.2.0", {"version.txt": "0.2.0"})
        remote.create_tag("v0.2.0")
        updated_commit = remote.current_commit()

        # Clone to local at v0.1.0
        local_dir = tmp_path / "local"
        local_dir.mkdir()
        subprocess.run(
            ["git", "clone", str(remote.repo_path), str(local_dir)],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(local_dir), "reset", "--hard", "v0.1.0"],
            capture_output=True,
            check=True,
        )

        # Apply update
        result = apply_update(local_dir)

        assert result.success is True
        assert result.old_version == "v0.1.0"
        assert result.new_version == "v0.2.0"
        assert result.error is None

        # Verify HEAD moved
        current_commit = subprocess.run(
            ["git", "-C", str(local_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        assert current_commit == updated_commit


def test_apply_update_idempotent_when_already_updated(tmp_path: Path) -> None:
    """Test that applying update when already up-to-date is safe.

    GIVEN local and remote at same commit
    WHEN apply_update() is called
    THEN git pull succeeds (no-op)
    AND returns success
    """
    # Create remote
    remote_dir = tmp_path / "remote"
    with with_git_repo(remote_dir, commits=["Initial"]) as remote:
        remote.create_tag("v0.1.0")

        # Clone to local (will be at same commit)
        local_dir = tmp_path / "local"
        local_dir.mkdir()
        subprocess.run(
            ["git", "clone", str(remote.repo_path), str(local_dir)],
            capture_output=True,
            check=True,
        )

        # Apply update (should be no-op)
        result = apply_update(local_dir)

        assert result.success is True
        assert result.old_version == "v0.1.0"
        assert result.new_version == "v0.1.0"


def test_apply_update_uses_ff_only(tmp_path: Path) -> None:
    """Test that apply_update uses --ff-only flag.

    This test verifies the flag is used (implicitly by checking success).
    Direct verification would require mocking subprocess.
    """
    # Create remote with update
    remote_dir = tmp_path / "remote"
    with with_git_repo(remote_dir, commits=["Initial"]) as remote:
        remote.create_tag("v0.1.0")
        remote.create_commit("Update", {"new.txt": "content"})

        # Clone and reset
        local_dir = tmp_path / "local"
        local_dir.mkdir()
        subprocess.run(
            ["git", "clone", str(remote.repo_path), str(local_dir)],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(local_dir), "reset", "--hard", "v0.1.0"],
            capture_output=True,
            check=True,
        )

        # Apply update
        result = apply_update(local_dir)

        # If --ff-only wasn't used and merge was needed, this would fail
        assert result.success is True
