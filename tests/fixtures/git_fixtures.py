"""
Git repository fixtures for testing update functionality.

Provides context managers and fixtures for creating temporary git repositories
with real git commands (not mocks), following ADR-003.

Usage:
    def test_update_detection(tmp_path):
        with with_git_repo(tmp_path, commits=["Initial"]) as repo:
            repo.create_tag("v0.1.0")
            repo.create_commit("Second", {"file.txt": "content"})
            assert repo.current_commit() != repo.get_commit("v0.1.0")
"""

from __future__ import annotations

import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Generator

if TYPE_CHECKING:
    from typing import Any


@dataclass
class GitRepo:
    """Represents a temporary git repository for testing.

    Attributes:
        repo_path: Path to repository root directory.
    """

    repo_path: Path

    def run_git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        """Execute a git command in this repository.

        Args:
            *args: Git command arguments (e.g., "status", "--porcelain").
            check: If True, raise on non-zero exit code.

        Returns:
            CompletedProcess with stdout, stderr, returncode.

        Example:
            result = repo.run_git("status", "--porcelain")
            assert result.returncode == 0
        """
        return subprocess.run(
            ["git", "-C", str(self.repo_path)] + list(args),
            capture_output=True,
            text=True,
            check=check,
        )

    def current_commit(self) -> str:
        """Get current commit hash.

        Returns:
            Full commit hash (40 characters).
        """
        result = self.run_git("rev-parse", "HEAD")
        return result.stdout.strip()

    def current_branch(self) -> str:
        """Get current branch name.

        Returns:
            Branch name (e.g., "main"), or "HEAD" if in detached HEAD state.
        """
        result = self.run_git("rev-parse", "--abbrev-ref", "HEAD", check=False)
        if result.returncode != 0:
            # No commits yet, return the configured init branch
            return "main"
        return result.stdout.strip()

    def get_commit(self, ref: str) -> str:
        """Get commit hash for a reference.

        Args:
            ref: Git reference (branch, tag, commit).

        Returns:
            Full commit hash (dereferenced if ref is an annotated tag).
        """
        # Use ^{commit} to dereference annotated tags to their commit
        result = self.run_git("rev-parse", f"{ref}^{{commit}}")
        return result.stdout.strip()

    def create_commit(
        self, message: str, files: dict[str, str] | None = None
    ) -> str:
        """Create a new commit with optional files.

        Args:
            message: Commit message.
            files: Dict mapping relative paths to file contents.

        Returns:
            New commit hash.

        Example:
            commit = repo.create_commit("Add file", {"src/main.py": "print('hello')"})
        """
        if files:
            for path, content in files.items():
                file_path = self.repo_path / path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content)
                self.run_git("add", path)

        self.run_git("commit", "--allow-empty", "-m", message)
        return self.current_commit()

    def create_tag(self, name: str, message: str | None = None) -> None:
        """Create an annotated tag at current commit.

        Args:
            name: Tag name (e.g., "v0.1.0").
            message: Tag message (defaults to tag name).
        """
        msg = message or name
        self.run_git("tag", "-a", name, "-m", msg)

    def checkout(self, ref: str) -> None:
        """Checkout a branch, tag, or commit.

        Args:
            ref: Git reference to checkout.
        """
        self.run_git("checkout", ref)

    def has_uncommitted_changes(self) -> bool:
        """Check if there are uncommitted changes.

        Returns:
            True if working directory has uncommitted changes.
        """
        result = self.run_git("status", "--porcelain")
        return bool(result.stdout.strip())

    def create_remote(self, name: str = "origin", url: str | None = None) -> None:
        """Add a remote to the repository.

        Args:
            name: Remote name (default: "origin").
            url: Remote URL (default: repo_path for local testing).
        """
        remote_url = url or str(self.repo_path)
        self.run_git("remote", "add", name, remote_url)


@contextmanager
def with_git_repo(
    tmp_path: Path,
    commits: list[str] | None = None,
    init_branch: str = "main",
) -> Generator[GitRepo, None, None]:
    """Context manager providing a temporary git repository.

    Creates a git repository in tmp_path with optional initial commits.
    Sets git user.name and user.email to avoid git config requirements.

    Args:
        tmp_path: Directory to create repository in (usually pytest tmp_path).
        commits: Optional list of commit messages to create initially.
        init_branch: Initial branch name (default: "main").

    Yields:
        GitRepo: Repository fixture with helper methods.

    Example:
        def test_version_detection(tmp_path):
            with with_git_repo(tmp_path, commits=["Initial"]) as repo:
                repo.create_tag("v0.1.0")
                assert repo.current_commit() == repo.get_commit("v0.1.0")
    """
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True, exist_ok=True)

    # Initialize repository
    subprocess.run(
        ["git", "init", "-b", init_branch, str(repo_path)],
        capture_output=True,
        check=True,
    )

    # Set user config (required for commits)
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.name", "Test User"],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.email", "test@example.com"],
        capture_output=True,
        check=True,
    )

    repo = GitRepo(repo_path=repo_path)

    # Create initial commits if specified
    if commits:
        for i, message in enumerate(commits):
            # Add a dummy file to make the commit non-empty
            dummy_file = f"file_{i}.txt"
            repo.create_commit(message, {dummy_file: f"Content for {message}"})

    try:
        yield repo
    finally:
        # Cleanup handled by pytest tmp_path fixture
        pass
