"""
Self-update functionality for cloud-mirror.

This module provides git-based self-update capabilities, allowing cloud-mirror
to automatically update itself from the GitHub repository.

Per ADR-002, updates use git fetch/pull for atomic operations with built-in
rollback capabilities.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class UpdateStatus:
    """Status of update check.

    Attributes:
        current_version: Currently installed version (from git describe).
        remote_version: Remote version from origin/main, or None if fetch failed.
        update_available: True if remote has newer commits than local.
        error: Error message if update check failed, or None if successful.
    """

    current_version: str | None
    remote_version: str | None
    update_available: bool
    error: str | None = None


@dataclass
class UpdateResult:
    """Result of update application.

    Attributes:
        success: True if update was applied successfully.
        old_version: Version before update, or None if not available.
        new_version: Version after update, or None if update failed.
        error: Error message if update failed, or None if successful.
    """

    success: bool
    old_version: str | None = None
    new_version: str | None = None
    error: str | None = None


def is_git_installation(repo_path: Path | None = None) -> bool:
    """Check if cloud-mirror is installed via git clone.

    Detects git installation by checking for .git directory. This is a
    filesystem check only - no git commands are executed.

    Args:
        repo_path: Path to cloud-mirror installation directory.
                   If None, uses current working directory.

    Returns:
        True if .git directory exists (git installation), False otherwise.

    Example:
        >>> is_git_installation(Path("/mnt/apps/cloud-mirror"))
        True
        >>> is_git_installation(Path("/tmp/copied-files"))
        False
    """
    if repo_path is None:
        repo_path = Path.cwd()

    git_dir = repo_path / ".git"
    return git_dir.exists() and git_dir.is_dir()


def get_installed_version(repo_path: Path | None = None) -> str:
    """Get current cloud-mirror version using git describe.

    Uses `git describe --tags --always` to get version information:
    - If at a tag: returns tag name (e.g., "v0.1.0")
    - If after a tag: returns tag-count-hash (e.g., "v0.1.0-3-gabcdef")
    - If no tags: returns short commit hash (--always fallback)

    Falls back to cloud_mirror.__version__ if git command fails.

    Args:
        repo_path: Path to cloud-mirror installation directory.
                   If None, uses current working directory.

    Returns:
        Version string from git describe or __version__ fallback.

    Example:
        >>> get_installed_version(Path("/mnt/apps/cloud-mirror"))
        "v0.1.0"
        >>> get_installed_version(Path("/mnt/apps/cloud-mirror"))
        "v0.1.0-5-g3a2b1c4"
    """
    if repo_path is None:
        repo_path = Path.cwd()

    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "describe", "--tags", "--always"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip()
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        # Fall back to module __version__ if git fails
        from cloud_mirror import __version__

        return __version__


def get_remote_version(repo_path: Path | None = None) -> str | None:
    """Get remote cloud-mirror version from origin/main.

    Fetches from origin and uses `git describe --tags --always` on origin/main
    to get the remote version.

    Args:
        repo_path: Path to cloud-mirror installation directory.
                   If None, uses current working directory.

    Returns:
        Version string from remote, or None if fetch fails or no remote configured.

    Example:
        >>> get_remote_version(Path("/mnt/apps/cloud-mirror"))
        "v0.2.0"
        >>> get_remote_version(Path("/no-remote"))
        None
    """
    if repo_path is None:
        repo_path = Path.cwd()

    try:
        # Fetch from origin (quietly, no output)
        subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "fetch",
                "origin",
                "main",
                "--tags",
                "--quiet",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,  # Network operation, longer timeout
        )

        # Describe origin/main
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "describe",
                "--tags",
                "--always",
                "origin/main",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip()

    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        # Network failure, no remote, or other git error - return None
        return None


def check_for_update(repo_path: Path | None = None) -> UpdateStatus | None:
    """Check if an update is available from the remote repository.

    Orchestrates version detection by:
    1. Checking if installation is via git (returns None if not)
    2. Getting installed version from local repository
    3. Fetching and getting remote version from origin/main
    4. Comparing commit hashes to determine if update is available

    Args:
        repo_path: Path to cloud-mirror installation directory.
                   If None, uses current working directory.

    Returns:
        UpdateStatus with version info and availability, or None if not a git install.

    Example:
        >>> status = check_for_update(Path("/mnt/apps/cloud-mirror"))
        >>> if status and status.update_available:
        ...     print(f"Update available: {status.current_version} -> {status.remote_version}")
    """
    if repo_path is None:
        repo_path = Path.cwd()

    # Check if this is a git installation
    if not is_git_installation(repo_path):
        return None

    # Get current version
    current_version = get_installed_version(repo_path)

    # Get remote version
    remote_version = get_remote_version(repo_path)

    # If remote fetch failed, return error status
    if remote_version is None:
        return UpdateStatus(
            current_version=current_version,
            remote_version=None,
            update_available=False,
            error="Failed to fetch remote version (network error or no remote configured)",
        )

    # Compare versions by getting commit hashes
    # Need to resolve both to commit hashes for accurate comparison
    try:
        local_commit = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()

        remote_commit = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "origin/main"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()

        update_available = local_commit != remote_commit

        return UpdateStatus(
            current_version=current_version,
            remote_version=remote_version,
            update_available=update_available,
            error=None,
        )

    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ) as e:
        return UpdateStatus(
            current_version=current_version,
            remote_version=remote_version,
            update_available=False,
            error=f"Failed to compare versions: {e}",
        )


def has_uncommitted_changes(repo_path: Path | None = None) -> bool:
    """Check if working directory has uncommitted changes.

    Uses `git status --porcelain` to detect any uncommitted changes including:
    - Modified files
    - New untracked files
    - Staged but uncommitted changes
    - Deleted files

    Args:
        repo_path: Path to git repository directory.
                   If None, uses current working directory.

    Returns:
        True if there are uncommitted changes, False if working directory is clean.

    Example:
        >>> has_uncommitted_changes(Path("/mnt/apps/cloud-mirror"))
        False
        >>> # After making changes...
        >>> has_uncommitted_changes(Path("/mnt/apps/cloud-mirror"))
        True
    """
    if repo_path is None:
        repo_path = Path.cwd()

    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        # If output is non-empty, there are uncommitted changes
        return bool(result.stdout.strip())
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        # If git command fails, assume dirty (safer default)
        return True


def apply_update(repo_path: Path | None = None) -> UpdateResult:
    """Apply update by pulling from origin/main.

    Safety checks before updating:
    1. Checks for uncommitted changes (aborts if dirty)
    2. Uses --ff-only to ensure atomic fast-forward merge

    Update sequence:
    1. Check for uncommitted changes (abort if found)
    2. Get current version (old_version)
    3. Fetch from origin
    4. Pull with --ff-only (atomic update)
    5. Get new version
    6. Return success result

    Args:
        repo_path: Path to git repository directory.
                   If None, uses current working directory.

    Returns:
        UpdateResult with success status, versions, and optional error message.

    Example:
        >>> result = apply_update(Path("/mnt/apps/cloud-mirror"))
        >>> if result.success:
        ...     print(f"Updated: {result.old_version} -> {result.new_version}")
        ... else:
        ...     print(f"Update failed: {result.error}")
    """
    if repo_path is None:
        repo_path = Path.cwd()

    # Check for uncommitted changes
    if has_uncommitted_changes(repo_path):
        return UpdateResult(
            success=False,
            error="Uncommitted changes detected. Commit or stash changes before updating.",
        )

    # Get current version before update
    old_version = get_installed_version(repo_path)

    try:
        # Fetch from origin
        subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "fetch",
                "origin",
                "main",
                "--tags",
                "--quiet",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

        # Pull with --ff-only (ensures atomic update, no merge commits)
        subprocess.run(
            ["git", "-C", str(repo_path), "pull", "--ff-only", "origin", "main"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

        # Get new version after update
        new_version = get_installed_version(repo_path)

        return UpdateResult(
            success=True,
            old_version=old_version,
            new_version=new_version,
            error=None,
        )

    except subprocess.CalledProcessError as e:
        return UpdateResult(
            success=False,
            old_version=old_version,
            new_version=None,
            error=f"Git pull failed: {e.stderr.strip() if e.stderr else str(e)}",
        )
    except subprocess.TimeoutExpired:
        return UpdateResult(
            success=False,
            old_version=old_version,
            new_version=None,
            error="Update timed out (network issue)",
        )
    except FileNotFoundError:
        return UpdateResult(
            success=False,
            old_version=old_version,
            new_version=None,
            error="Git command not found",
        )


def reexec_with_new_code() -> None:
    """Re-execute cloud-mirror with updated code.

    Uses os.execv() to replace the current process with a new Python interpreter
    running the updated code. This preserves the process ID and provides a clean
    transition to the new code without leaving orphaned processes.

    Command-line arguments from sys.argv are preserved, ensuring the sync operation
    continues with the same parameters after the update.

    On failure (e.g., permission denied, Python executable not found), the function
    logs an error and returns normally, allowing the caller to continue with the
    current code.

    Note:
        This function does not return if successful - the current process is
        replaced by os.execv(). Only returns on failure.

    Example:
        >>> # After successful update
        >>> reexec_with_new_code()
        >>> # Process is replaced, this line never executes

        >>> # On failure, execution continues
        >>> reexec_with_new_code()  # Logs error and returns
        >>> print("Continuing with old code")  # This executes
    """
    try:
        # Construct command: [python, -m, cloud_mirror, ...original_args]
        # sys.argv[0] is the script name, sys.argv[1:] are the arguments
        args = [sys.executable, "-m", "cloud_mirror"] + sys.argv[1:]

        logger.info(f"Re-executing with updated code: {' '.join(args)}")

        # Replace current process with new Python interpreter
        # This is why we use os.execv instead of subprocess:
        # - Atomically replaces process (no subprocess management needed)
        # - Preserves PID (important for cron jobs and logging)
        # - Clean transition (no old process lingering in background)
        os.execv(sys.executable, args)

        # Note: This line never executes if execv succeeds

    except OSError as e:
        # Handle failures gracefully (permission denied, file not found, etc.)
        logger.error(f"Failed to re-execute: {e}")
        # Return normally - caller can decide how to handle
        # (typically: continue with old code, log warning to user)
