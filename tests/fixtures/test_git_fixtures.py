"""Tests for git_fixtures module to verify fixtures work correctly."""

from pathlib import Path

import pytest

from tests.fixtures.git_fixtures import with_git_repo


def test_git_repo_initialization(tmp_path: Path) -> None:
    """Test that git repository initializes correctly."""
    with with_git_repo(tmp_path) as repo:
        assert repo.repo_path.exists()
        assert (repo.repo_path / ".git").exists()
        assert repo.current_branch() == "main"


def test_create_commit(tmp_path: Path) -> None:
    """Test creating commits with files."""
    with with_git_repo(tmp_path) as repo:
        # Create a commit with files
        commit = repo.create_commit(
            "Add test file",
            {"test.txt": "hello world", "subdir/file.py": "print('test')"},
        )

        assert len(commit) == 40  # Full SHA-1 hash
        assert (repo.repo_path / "test.txt").read_text() == "hello world"
        assert (repo.repo_path / "subdir" / "file.py").read_text() == "print('test')"


def test_create_tag(tmp_path: Path) -> None:
    """Test creating annotated tags."""
    with with_git_repo(tmp_path, commits=["Initial"]) as repo:
        initial_commit = repo.current_commit()
        repo.create_tag("v0.1.0", "Version 0.1.0")

        # Verify tag exists
        result = repo.run_git("tag", "-l")
        assert "v0.1.0" in result.stdout

        # Verify tag points to the commit it was created on
        assert repo.get_commit("v0.1.0") == initial_commit


def test_uncommitted_changes_detection(tmp_path: Path) -> None:
    """Test detection of uncommitted changes."""
    with with_git_repo(tmp_path, commits=["Initial"]) as repo:
        # Clean state
        assert not repo.has_uncommitted_changes()

        # Create uncommitted file
        (repo.repo_path / "new_file.txt").write_text("uncommitted")
        assert repo.has_uncommitted_changes()

        # Stage but don't commit
        repo.run_git("add", "new_file.txt")
        assert repo.has_uncommitted_changes()

        # Commit
        repo.run_git("commit", "-m", "Add file")
        assert not repo.has_uncommitted_changes()


def test_initial_commits(tmp_path: Path) -> None:
    """Test creating repository with initial commits."""
    with with_git_repo(tmp_path, commits=["First", "Second", "Third"]) as repo:
        # Should have 3 commits
        result = repo.run_git("log", "--oneline")
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 3

        # Commits should be in reverse order (newest first)
        assert "Third" in lines[0]
        assert "Second" in lines[1]
        assert "First" in lines[2]


def test_checkout(tmp_path: Path) -> None:
    """Test checking out different refs."""
    with with_git_repo(tmp_path, commits=["Initial"]) as repo:
        # Create and tag a commit
        commit1 = repo.current_commit()
        repo.create_tag("v1.0.0")

        # Create another commit
        repo.create_commit("Second", {"file2.txt": "content"})
        commit2 = repo.current_commit()

        assert commit1 != commit2

        # Checkout tag
        repo.checkout("v1.0.0")
        assert repo.current_commit() == commit1

        # Checkout main branch
        repo.checkout("main")
        assert repo.current_commit() == commit2


def test_fixture_usage(git_repo) -> None:
    """Test using git_repo as a pytest fixture."""
    # Should work with the pytest fixture
    git_repo.create_commit("Test commit", {"fixture_test.txt": "works"})
    assert (git_repo.repo_path / "fixture_test.txt").read_text() == "works"
