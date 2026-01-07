"""Tests for update detection orchestration (FR4 of story-32)."""

from pathlib import Path

import pytest

from cloud_mirror.update import UpdateStatus, check_for_update
from tests.fixtures.git_fixtures import with_git_repo


def test_check_for_update_when_update_available(tmp_path: Path) -> None:
    """Test that check_for_update detects available updates.

    GIVEN local version is v0.1.0 and remote version is v0.2.0
    WHEN check_for_update() is called
    THEN it returns UpdateStatus with update_available=True
    """
    import subprocess

    # Create remote with newer version
    remote_dir = tmp_path / "remote"
    with with_git_repo(remote_dir, commits=["Initial"]) as remote:
        remote.create_tag("v0.1.0")
        initial_commit = remote.current_commit()
        remote.create_commit("Update to v0.2.0", {"version.txt": "0.2.0"})
        remote.create_tag("v0.2.0")

        # Clone remote to create local (ensures shared history)
        local_dir = tmp_path / "local"
        local_dir.mkdir()
        subprocess.run(
            ["git", "clone", str(remote.repo_path), str(local_dir)],
            capture_output=True,
            check=True,
        )

        # Reset local to v0.1.0 (simulating being behind)
        subprocess.run(
            ["git", "-C", str(local_dir), "reset", "--hard", initial_commit],
            capture_output=True,
            check=True,
        )

        # Check for update
        status = check_for_update(local_dir)

        assert status is not None
        assert status.current_version == "v0.1.0"
        assert status.remote_version == "v0.2.0"
        assert status.update_available is True
        assert status.error is None


def test_check_for_update_when_already_up_to_date(tmp_path: Path) -> None:
    """Test that check_for_update detects when already up-to-date.

    GIVEN local and remote both at v0.1.0
    WHEN check_for_update() is called
    THEN it returns UpdateStatus with update_available=False
    """
    import subprocess

    # Create remote at v0.1.0
    remote_dir = tmp_path / "remote"
    with with_git_repo(remote_dir, commits=["Initial"]) as remote:
        remote.create_tag("v0.1.0")

        # Clone remote to create local (ensures shared history)
        local_dir = tmp_path / "local"
        local_dir.mkdir()
        subprocess.run(
            ["git", "clone", str(remote.repo_path), str(local_dir)],
            capture_output=True,
            check=True,
        )

        status = check_for_update(local_dir)

        assert status is not None
        assert status.current_version == "v0.1.0"
        assert status.remote_version == "v0.1.0"
        assert status.update_available is False
        assert status.error is None


def test_check_for_update_for_non_git_installation(tmp_path: Path) -> None:
    """Test that check_for_update returns None for non-git installations.

    GIVEN cloud-mirror installed by copying files (no .git directory)
    WHEN check_for_update() is called
    THEN it returns None
    AND no git commands are attempted
    """
    # Create non-git directory
    non_git_dir = tmp_path / "cloud_mirror"
    non_git_dir.mkdir()

    status = check_for_update(non_git_dir)

    assert status is None


def test_check_for_update_handles_network_failure(tmp_path: Path) -> None:
    """Test graceful handling of network failures.

    GIVEN git fetch fails due to network error
    WHEN check_for_update() is called
    THEN it returns UpdateStatus with error set
    AND update_available is False
    """
    with with_git_repo(tmp_path, commits=["Initial"]) as repo:
        repo.create_tag("v0.1.0")
        # Add invalid remote
        repo.run_git("remote", "add", "origin", "https://invalid.example.com/repo.git")

        status = check_for_update(repo.repo_path)

        assert status is not None
        assert status.current_version == "v0.1.0"
        assert status.remote_version is None
        assert status.update_available is False
        assert status.error is not None
        assert "network" in status.error.lower() or "remote" in status.error.lower()


def test_check_for_update_compares_commit_hashes(tmp_path: Path) -> None:
    """Test that update detection uses commit hash comparison.

    GIVEN remote has newer commits (different commit hash)
    WHEN check_for_update() is called
    THEN it detects update is available based on commit difference
    """
    # Create remote repository
    remote_dir = tmp_path / "remote"
    with with_git_repo(remote_dir, commits=["Initial"]) as remote:
        remote.create_tag("v0.1.0")
        initial_commit = remote.current_commit()

        # Add more commits to remote
        remote.create_commit("Second", {"file2.txt": "content"})
        remote.create_commit("Third", {"file3.txt": "content"})

        # Create local as a clone of remote, then reset to initial commit
        local_dir = tmp_path / "local"
        local_dir.mkdir()

        # Clone the remote
        import subprocess

        subprocess.run(
            ["git", "clone", str(remote.repo_path), str(local_dir)],
            capture_output=True,
            check=True,
        )

        # Reset local to the initial commit (simulating it's behind)
        subprocess.run(
            ["git", "-C", str(local_dir), "reset", "--hard", initial_commit],
            capture_output=True,
            check=True,
        )

        status = check_for_update(local_dir)

        assert status is not None
        assert status.update_available is True


def test_update_status_dataclass() -> None:
    """Test UpdateStatus dataclass structure."""
    # Test with all fields
    status = UpdateStatus(
        current_version="v0.1.0",
        remote_version="v0.2.0",
        update_available=True,
        error=None,
    )
    assert status.current_version == "v0.1.0"
    assert status.remote_version == "v0.2.0"
    assert status.update_available is True
    assert status.error is None

    # Test with error
    error_status = UpdateStatus(
        current_version="v0.1.0",
        remote_version=None,
        update_available=False,
        error="Network failure",
    )
    assert error_status.error == "Network failure"
