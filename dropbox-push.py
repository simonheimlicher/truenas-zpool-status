#!/usr/bin/env python3

"""
ZFS Snapshot Dropbox Push Script for TrueNAS SCALE

Creates a recursive ZFS snapshot, clones the entire dataset tree to ensure
consistent traversal of nested datasets, pushes to Dropbox via rclone,
and cleans up.

This solves the problem where TrueNAS SCALE's built-in Cloud Sync Tasks fail
on datasets with nested child datasets because files change during sync.

Consistency: We clone the snapshot tree rather than traversing .zfs/snapshot,
which would still show live child dataset mountpoints instead of their snapshot
contents. The clone tree provides a truly immutable, consistent view.

Requirements:
    - TrueNAS SCALE 25.10+ (Python 3.11+, rclone pre-installed)
    - rclone configured with your Dropbox account
    - ZFS dataset to back up

Usage:
    /mnt/system/admin/dropbox-push/dropbox-push.py apps/config dropbox:TrueNAS-Backup/apps-config --rclone-config /mnt/system/admin/dropbox-push/rclone.conf
    /mnt/system/admin/dropbox-push/dropbox-push.py apps/data dropbox:TrueNAS-Backup/apps-data --rclone-config /mnt/system/admin/dropbox-push/rclone.conf --dry-run -v
    /mnt/system/admin/dropbox-push/dropbox-push.py apps/config dropbox:Backup --rclone-config /mnt/system/admin/dropbox-push/rclone.conf --keep-versions 3

Author: Simon Heimlicher
License: MIT
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import logging
import os
import re
import signal
import subprocess
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from types import FrameType, TracebackType
from typing import TextIO

# Global state for signal handling
_terminate_requested = False
_active_child_process: subprocess.Popen[str] | None = None

# Constants
DEFAULT_TRANSFERS = 4  # Conservative default for Dropbox rate limits
SNAPSHOT_PREFIX = "dropboxpush"
CLONE_SUFFIX = ".dropboxpush"
VERSIONS_DIR = ".versions"
RCLONE_BIN = "/usr/bin/rclone"
RCLONE_CONFIG_FILENAME = "rclone.conf"
LOCK_DIR = Path("/run")
# ZFS user property to tag our clones (prevents accidental deletion of unrelated datasets)
ZFS_USER_PROPERTY = "ch.srvr.dropboxpush:managed"
ZFS_USER_PROPERTY_VALUE = "true"


def get_script_dir() -> Path:
    """Get the directory containing this script.

    If the script is invoked via a symlink, returns the symlink's directory,
    not the original file's directory. This allows placing rclone.conf next
    to the symlink.
    """
    # sys.argv[0] gives the path as invoked (preserves symlinks)
    # os.path.abspath makes it absolute without resolving symlinks
    return Path(os.path.abspath(sys.argv[0])).parent


def get_default_rclone_config() -> Path:
    """Get the default rclone config path (same directory as script)."""
    return get_script_dir() / RCLONE_CONFIG_FILENAME

# Timeouts (seconds) - ZFS recursive operations can take much longer on large datasets
TIMEOUT_ZFS_QUICK = 60  # Simple queries (get, list single dataset)
TIMEOUT_ZFS_RECURSIVE = 1800  # Recursive operations (snapshot -r, destroy -r, clone tree)
TIMEOUT_RCLONE_QUICK = 60  # Quick rclone commands (listremotes, lsf)


class DropboxPushError(Exception):
    """Custom exception for cloud sync operations."""


class TerminatedError(Exception):
    """Raised when the process receives a termination signal."""


def _handle_termination_signal(signum: int, _frame: FrameType | None) -> None:
    """Handle SIGTERM/SIGHUP by setting flag and terminating child processes."""
    global _terminate_requested, _active_child_process
    _terminate_requested = True
    if _active_child_process is not None:
        try:
            _active_child_process.terminate()
        except OSError:
            pass  # Process may have already exited


def check_termination() -> None:
    """Check if termination was requested and raise if so."""
    if _terminate_requested:
        raise TerminatedError("Termination requested by signal")


def sanitize_for_filename(name: str) -> str:
    """Sanitize a string for safe use in filenames.

    Replaces path separators and removes potentially dangerous sequences.
    Appends a short hash to prevent collisions (e.g., "a.b" vs "a/b" both
    becoming "a_b").
    """
    # Replace path separators with underscores
    safe = name.replace("/", "_").replace("\\", "_")
    # Remove any remaining dots that could cause path traversal
    safe = re.sub(r"\.+", "_", safe)
    # Remove any other non-alphanumeric characters except underscore and hyphen
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", safe)
    # Collapse multiple underscores
    safe = re.sub(r"_+", "_", safe)
    # Strip leading/trailing underscores
    safe = safe.strip("_")

    # Add short hash of original name to prevent collisions
    # e.g., "foo.bar" and "foo/bar" would both sanitize to "foo_bar"
    name_hash = hashlib.sha256(name.encode()).hexdigest()[:8]
    return f"{safe}-{name_hash}"


class LockFile:
    """Context manager for file-based locking to prevent concurrent runs."""

    def __init__(self, dataset: str, logger: logging.Logger):
        # Sanitize dataset name for use in filename
        safe_name = sanitize_for_filename(dataset)
        self.lock_path = LOCK_DIR / f"dropbox-push.{safe_name}.lock"
        self.lock_fd: TextIO | None = None
        self.logger = logger

    def __enter__(self) -> "LockFile":
        self.logger.debug(f"Acquiring lock: {self.lock_path}")
        self.lock_fd = open(self.lock_path, "w", encoding="utf-8")
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.logger.debug("Lock acquired")
            return self
        except BlockingIOError:
            self.lock_fd.close()
            self.lock_fd = None
            raise DropboxPushError(
                f"Another sync is already running for this dataset.\n"
                f"Lock file: {self.lock_path}\n"
                f"If this is incorrect, remove the lock file and retry."
            )
        except Exception:
            # Ensure fd is closed on any other exception (PermissionError, OSError, etc.)
            self.lock_fd.close()
            self.lock_fd = None
            raise

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self.lock_fd:
            fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
            self.lock_fd.close()
            try:
                self.lock_path.unlink()
            except OSError:
                pass
            self.logger.debug("Lock released")


def setup_logging(verbose: bool = False, debug: bool = False) -> logging.Logger:
    """Configure logging based on verbosity level.

    Default (no flags): Only errors go to stderr
    --verbose: Info and above go to stderr
    --debug: Debug and above go to stderr
    """
    logger = logging.getLogger("dropbox-push")

    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.ERROR

    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)

    if debug:
        fmt = "%(asctime)s [%(levelname)s] %(message)s"
    else:
        fmt = "%(message)s"

    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)

    return logger


def run_command(
    cmd: list[str],
    logger: logging.Logger,
    check: bool = True,
    capture_output: bool = True,
    timeout: int | None = TIMEOUT_ZFS_QUICK,
) -> subprocess.CompletedProcess[str]:
    """Run a command and handle errors.

    Args:
        cmd: Command and arguments to run
        logger: Logger instance
        check: Raise exception on non-zero exit code
        capture_output: Capture stdout/stderr
        timeout: Timeout in seconds (default: TIMEOUT_ZFS_QUICK for simple ops,
                 use TIMEOUT_ZFS_RECURSIVE for recursive ZFS operations)
    """
    logger.debug(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            check=check,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
        )
        if result.stdout and logger.isEnabledFor(logging.DEBUG):
            for line in result.stdout.strip().split("\n")[:10]:  # Limit output
                logger.debug(f"  stdout: {line}")
        return result
    except subprocess.TimeoutExpired as e:
        logger.debug(f"Command timed out after {timeout}s: {' '.join(cmd)}")
        raise DropboxPushError(
            f"Command timed out after {timeout} seconds: {' '.join(cmd)}"
        ) from e
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        logger.debug(f"Command failed: {' '.join(cmd)}")
        raise DropboxPushError(
            f"Command failed with exit code {e.returncode}: {error_msg}"
        ) from e


def generate_timestamp() -> str:
    """Generate a UTC timestamp for snapshot/version naming.

    Uses seconds for collision safety.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def validate_dataset(dataset: str, logger: logging.Logger) -> Path:
    """Validate that the ZFS dataset exists and return its mountpoint."""
    logger.info(f"Validating dataset: {dataset}")

    result = run_command(
        ["zfs", "get", "-H", "-o", "value", "mountpoint", dataset],
        logger,
        check=False,
    )

    if result.returncode != 0:
        raise DropboxPushError(f"Dataset '{dataset}' does not exist or is not accessible")

    mountpoint = result.stdout.strip()

    if mountpoint in ("none", "-", ""):
        raise DropboxPushError(f"Dataset '{dataset}' has no mountpoint (mountpoint={mountpoint})")

    mountpoint_path = Path(mountpoint)
    if not mountpoint_path.exists():
        raise DropboxPushError(f"Mountpoint '{mountpoint}' does not exist on filesystem")

    logger.debug(f"Dataset mountpoint: {mountpoint}")
    return mountpoint_path


def validate_rclone_config(config_path: Path, logger: logging.Logger) -> None:
    """Validate that rclone config file exists."""
    if not config_path.exists():
        raise DropboxPushError(
            f"rclone config not found: {config_path}\n"
            f"Please create it with: rclone config --config {config_path}\n"
            f"Or specify a different path with: --rclone-config /path/to/rclone.conf"
        )
    logger.debug(f"Using rclone config: {config_path}")


def validate_rclone_remote(
    remote: str,
    config_path: Path,
    logger: logging.Logger,
) -> None:
    """Validate that the rclone remote exists and is accessible."""
    if ":" not in remote:
        raise DropboxPushError(
            f"Invalid remote format: '{remote}'\n"
            f"Expected format: remote:path (e.g., 'dropbox:TrueNAS-Backup/apps-config')"
        )

    remote_name = remote.split(":")[0]
    logger.info(f"Validating rclone remote: {remote_name}")

    result = run_command(
        [RCLONE_BIN, "--config", str(config_path), "listremotes"],
        logger,
    )

    available_remotes = [r.rstrip(":") for r in result.stdout.strip().split("\n") if r]

    if remote_name not in available_remotes:
        raise DropboxPushError(
            f"Remote '{remote_name}' not found in rclone config.\n"
            f"Available remotes: {', '.join(available_remotes) or '(none)'}\n"
            f"Configure it with: rclone config --config {config_path}"
        )

    logger.debug(f"Remote '{remote_name}' found in config")


# Valid ZFS dataset name pattern: alphanumeric, underscore, hyphen, dot, colon, slash
# Must not contain @ (snapshot separator) or start/end with slash
DATASET_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-.:]*(/[a-zA-Z0-9][a-zA-Z0-9_\-.:]*)*$")


def validate_dataset_name(dataset: str, logger: logging.Logger) -> None:
    """Validate that the dataset name has a safe format.

    Prevents potential issues with malformed dataset names containing
    snapshot separators (@) or other problematic characters.
    """
    if not dataset:
        raise DropboxPushError("Dataset name cannot be empty")

    if "@" in dataset:
        raise DropboxPushError(
            f"Invalid dataset name: '{dataset}'\n"
            f"Dataset name cannot contain '@' (snapshot separator)"
        )

    if not DATASET_NAME_PATTERN.match(dataset):
        raise DropboxPushError(
            f"Invalid dataset name format: '{dataset}'\n"
            f"Dataset names must start with alphanumeric and contain only "
            f"alphanumeric, underscore, hyphen, dot, colon, or slash characters"
        )

    logger.debug(f"Dataset name validated: {dataset}")


def list_datasets_recursive(root_dataset: str, logger: logging.Logger) -> list[str]:
    """List all datasets under and including the root dataset.

    Returns:
        List of dataset names, sorted (parent before children)
    """
    logger.debug(f"Enumerating datasets under: {root_dataset}")

    result = run_command(
        ["zfs", "list", "-H", "-r", "-o", "name", root_dataset],
        logger,
    )

    datasets = [ds.strip() for ds in result.stdout.strip().split("\n") if ds.strip()]
    logger.debug(f"Found {len(datasets)} datasets")

    return sorted(datasets)


def find_stale_snapshots(
    root_dataset: str,
    snapshot_name: str,
    logger: logging.Logger,
) -> list[str]:
    """Find any existing snapshots with the given name under root_dataset.

    Returns list of full snapshot names (dataset@snapshot) that exist.
    This catches stale snapshots on child datasets that would cause
    'zfs snapshot -r' to fail.
    """
    # Use zfs list -r to check all datasets under root for this snapshot name
    result = run_command(
        ["zfs", "list", "-H", "-r", "-t", "snapshot", "-o", "name", root_dataset],
        logger,
        check=False,
    )

    if result.returncode != 0:
        return []

    # Filter for snapshots matching our snapshot name
    stale = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        # Line format: "dataset@snapshot"
        if "@" in line and line.split("@")[1] == snapshot_name:
            stale.append(line)

    return stale


def destroy_stale_snapshots(
    root_dataset: str,
    snapshot_name: str,
    stale_snapshots: list[str],
    logger: logging.Logger,
) -> None:
    """Destroy stale snapshots, handling the case where only children exist.

    First tries recursive destroy from root (efficient if root snapshot exists).
    If that fails, falls back to destroying individual snapshots.
    """
    full_snapshot = f"{root_dataset}@{snapshot_name}"

    # Check if root snapshot exists - if so, recursive destroy will work
    root_exists = full_snapshot in stale_snapshots

    if root_exists:
        # Root exists, recursive destroy should work
        result = run_command(
            ["zfs", "destroy", "-r", full_snapshot],
            logger,
            check=False,
            timeout=TIMEOUT_ZFS_RECURSIVE,
        )
        if result.returncode == 0:
            return
        logger.debug("Recursive destroy failed, falling back to individual destruction")

    # Fall back to destroying individual snapshots (children only, or recursive failed)
    # Destroy in reverse order (children before parents) to avoid dependency issues
    for snap in sorted(stale_snapshots, reverse=True):
        result = run_command(
            ["zfs", "destroy", snap],
            logger,
            check=False,
            timeout=TIMEOUT_ZFS_QUICK,
        )
        if result.returncode != 0:
            logger.warning(f"Failed to destroy stale snapshot: {snap}")


def create_recursive_snapshot(
    root_dataset: str,
    snapshot_name: str,
    logger: logging.Logger,
) -> None:
    """Create a recursive ZFS snapshot."""
    # Check for termination before starting
    check_termination()

    full_snapshot = f"{root_dataset}@{snapshot_name}"

    # Check for existing snapshots on any dataset in the tree
    # (not just root - child datasets could have stale snapshots too)
    stale_snapshots = find_stale_snapshots(root_dataset, snapshot_name, logger)
    if stale_snapshots:
        logger.warning(
            f"Found {len(stale_snapshots)} stale snapshot(s), destroying: "
            f"{', '.join(stale_snapshots[:3])}{'...' if len(stale_snapshots) > 3 else ''}"
        )
        # Try recursive destroy first (works if root snapshot exists)
        # If that fails (only children exist), destroy individually
        destroy_stale_snapshots(root_dataset, snapshot_name, stale_snapshots, logger)

    logger.info(f"Creating recursive snapshot: {full_snapshot}")
    run_command(["zfs", "snapshot", "-r", full_snapshot], logger, timeout=TIMEOUT_ZFS_RECURSIVE)


def destroy_recursive_snapshot(
    root_dataset: str,
    snapshot_name: str,
    logger: logging.Logger,
) -> None:
    """Destroy a recursive ZFS snapshot."""
    full_snapshot = f"{root_dataset}@{snapshot_name}"
    logger.info(f"Destroying recursive snapshot: {full_snapshot}")

    result = run_command(
        ["zfs", "destroy", "-r", full_snapshot],
        logger,
        check=False,
        timeout=TIMEOUT_ZFS_RECURSIVE,
    )

    if result.returncode != 0:
        logger.warning(f"Failed to destroy snapshot (may need manual cleanup): {full_snapshot}")


def get_clone_dataset_name(root_dataset: str) -> str:
    """Derive the clone root dataset name from the source dataset.

    Example: apps/config -> apps/config.dropboxpush
    """
    return f"{root_dataset}{CLONE_SUFFIX}"


def get_pool_name(dataset: str) -> str:
    """Extract the pool name from a dataset name.

    Example: apps/config/foo -> apps
    """
    return dataset.split("/")[0]


def get_pool_altroot(pool: str, logger: logging.Logger) -> Path | None:
    """Get the altroot property of a ZFS pool.

    TrueNAS SCALE sets altroot=/mnt on pools. When setting mountpoints,
    ZFS prepends the altroot, so we need to strip it from our paths.

    Returns:
        Path to altroot if set, None if not set or on error.
    """
    result = run_command(
        ["zpool", "get", "-H", "-o", "value", "altroot", pool],
        logger,
        check=False,
    )

    if result.returncode != 0:
        return None

    altroot = result.stdout.strip()
    if altroot in ("-", ""):
        return None

    logger.debug(f"Pool '{pool}' has altroot: {altroot}")
    return Path(altroot)


def get_clone_mountpoint(root_mountpoint: Path) -> Path:
    """Derive the clone mountpoint from the source mountpoint.

    Example: /mnt/apps/config -> /mnt/apps/config.dropboxpush
    """
    return root_mountpoint.parent / f"{root_mountpoint.name}{CLONE_SUFFIX}"


def strip_altroot(mountpoint: Path, altroot: Path | None) -> Path:
    """Strip altroot prefix from a mountpoint for use with zfs clone -o mountpoint.

    When a pool has altroot set (e.g., /mnt on TrueNAS), ZFS prepends it to
    any mountpoint you specify. So to get /mnt/apps/config.dropboxpush,
    you need to specify /apps/config.dropboxpush.

    Args:
        mountpoint: The desired filesystem path (e.g., /mnt/apps/config.dropboxpush)
        altroot: The pool's altroot (e.g., /mnt), or None if not set

    Returns:
        The path to pass to zfs clone -o mountpoint=
    """
    if altroot is None:
        return mountpoint

    try:
        # Check if mountpoint starts with altroot
        relative = mountpoint.relative_to(altroot)
        # Return as absolute path without the altroot prefix
        return Path("/") / relative
    except ValueError:
        # mountpoint doesn't start with altroot, use as-is
        return mountpoint


def create_clone_tree(
    root_dataset: str,
    datasets: list[str],
    snapshot_name: str,
    clone_root: str,
    clone_mountpoint: Path,
    altroot: Path | None,
    logger: logging.Logger,
) -> None:
    """Create a clone tree from snapshots of all datasets.

    For each dataset, creates a clone of its snapshot under the clone root,
    with proper mountpoints that mirror the original structure.

    Args:
        root_dataset: The source root dataset name
        datasets: List of all datasets to clone (including root)
        snapshot_name: Name of the snapshot to clone from
        clone_root: Name for the clone root dataset
        clone_mountpoint: Desired filesystem path for the clone root
        altroot: Pool's altroot property (mountpoints are adjusted for this)
        logger: Logger instance
    """
    logger.info(f"Creating clone tree: {clone_root} -> {clone_mountpoint}")

    for dataset in datasets:
        # Check for termination before each clone operation
        check_termination()

        # Calculate relative path from root dataset
        # Example: dataset="apps/config/audiobookshelf/config", root="apps/config"
        #          -> relative="audiobookshelf/config"
        if dataset == root_dataset:
            relative = ""
        else:
            # Use removeprefix for clarity and safety
            relative = dataset.removeprefix(root_dataset + "/")

        # Determine clone dataset name and mountpoint
        if relative:
            clone_dataset = f"{clone_root}/{relative}"
            clone_mp = clone_mountpoint / relative
        else:
            clone_dataset = clone_root
            clone_mp = clone_mountpoint

        # Adjust mountpoint for altroot (TrueNAS prepends altroot to mountpoint)
        zfs_mountpoint = strip_altroot(clone_mp, altroot)

        snapshot_full = f"{dataset}@{snapshot_name}"

        logger.debug(f"Cloning {snapshot_full} -> {clone_dataset} ({clone_mp})")

        # Create the clone with our user property for safe identification
        run_command(
            [
                "zfs", "clone",
                "-o", f"mountpoint={zfs_mountpoint}",
                "-o", "readonly=on",
                "-o", f"{ZFS_USER_PROPERTY}={ZFS_USER_PROPERTY_VALUE}",
                snapshot_full,
                clone_dataset,
            ],
            logger,
        )

    logger.debug("Clone tree created successfully")

    # Check if root clone is mounted - if so, assume children are too (ZFS auto-mounted them)
    # If not, explicitly mount each clone (some systems don't auto-mount)
    root_mount_check = run_command(
        ["zfs", "get", "-H", "-o", "value", "mounted", clone_root],
        logger,
        check=False,
    )
    if root_mount_check.returncode == 0 and root_mount_check.stdout.strip() == "yes":
        logger.debug("Clone tree auto-mounted successfully")
        return

    # Root not mounted - mount all clones explicitly
    logger.debug(f"Mounting clone tree (not auto-mounted): {clone_root}")
    for dataset in datasets:
        check_termination()

        if dataset == root_dataset:
            clone_dataset = clone_root
        else:
            relative = dataset.removeprefix(root_dataset + "/")
            clone_dataset = f"{clone_root}/{relative}"

        mount_result = run_command(
            ["zfs", "mount", clone_dataset],
            logger,
            check=False,
        )
        if mount_result.returncode != 0:
            logger.warning(f"Failed to mount clone: {clone_dataset}")


def is_our_clone(dataset: str, logger: logging.Logger) -> bool:
    """Check if a dataset is a clone created by this script.

    Primary check: looks for our ZFS user property (ch.srvr.dropboxpush:managed=true).
    Fallback: checks if origin snapshot has our prefix (for backward compatibility).
    """
    # Primary check: user property (most reliable)
    prop_result = run_command(
        ["zfs", "get", "-H", "-o", "value", ZFS_USER_PROPERTY, dataset],
        logger,
        check=False,
    )

    if prop_result.returncode == 0:
        prop_value = prop_result.stdout.strip()
        if prop_value == ZFS_USER_PROPERTY_VALUE:
            return True

    # Fallback: check origin snapshot prefix (backward compatibility)
    origin_result = run_command(
        ["zfs", "get", "-H", "-o", "value", "origin", dataset],
        logger,
        check=False,
    )

    if origin_result.returncode != 0:
        return False

    origin = origin_result.stdout.strip()
    if origin in ("-", ""):
        # Not a clone (no origin)
        return False

    # Origin format: "pool/dataset@snapshot-name"
    # Check if the snapshot name has our prefix
    if "@" in origin:
        snapshot_name = origin.split("@")[1]
        return snapshot_name.startswith(SNAPSHOT_PREFIX)

    return False


def destroy_clone_tree(clone_root: str, logger: logging.Logger) -> None:
    """Destroy the entire clone tree recursively."""
    logger.info(f"Destroying clone tree: {clone_root}")

    # Check if it exists first
    check_result = run_command(
        ["zfs", "list", "-H", clone_root],
        logger,
        check=False,
    )

    if check_result.returncode != 0:
        logger.debug("Clone tree does not exist, nothing to destroy")
        return

    # Force unmount first to release any file handles (e.g., from interrupted rclone)
    run_command(
        ["zfs", "unmount", "-f", clone_root],
        logger,
        check=False,
    )

    # Destroy recursively with force to handle busy datasets
    result = run_command(
        ["zfs", "destroy", "-rf", clone_root],
        logger,
        check=False,
        timeout=TIMEOUT_ZFS_RECURSIVE,
    )

    if result.returncode != 0:
        logger.warning(f"Failed to destroy clone tree (may need manual cleanup): {clone_root}")
    else:
        logger.debug("Clone tree destroyed successfully")


def cleanup_old_versions(
    destination: str,
    keep_versions: int,
    config_path: Path,
    dry_run: bool,
    logger: logging.Logger,
) -> None:
    """Remove old version directories, keeping only the N most recent.

    Args:
        destination: rclone destination (e.g., 'dropbox:Backup/apps-config')
        keep_versions: Number of versions to keep (0 = disable versioning cleanup)
        config_path: Path to rclone config
        dry_run: If True, only log what would be deleted
        logger: Logger instance
    """
    if keep_versions <= 0:
        return

    versions_path = f"{destination}/{VERSIONS_DIR}"
    logger.info(f"Cleaning up old versions (keeping {keep_versions})")

    # List version directories
    result = run_command(
        [RCLONE_BIN, "--config", str(config_path), "lsf", "--dirs-only", versions_path],
        logger,
        check=False,
    )

    if result.returncode != 0:
        logger.debug("No versions directory found or error listing versions")
        return

    # Parse and sort version directories (format: YYYY-MM-DDTHH-MM-SSZ/)
    versions = sorted(
        [v.rstrip("/") for v in result.stdout.strip().split("\n") if v.strip()],
        reverse=True,  # Newest first
    )

    if len(versions) <= keep_versions:
        logger.debug(f"Found {len(versions)} versions, no cleanup needed")
        return

    # Delete old versions
    to_delete = versions[keep_versions:]
    logger.info(f"Removing {len(to_delete)} old version(s)")

    for version in to_delete:
        version_full_path = f"{versions_path}/{version}"
        logger.debug(f"Deleting: {version_full_path}")

        if dry_run:
            logger.info(f"[DRY RUN] Would delete: {version_full_path}")
            continue

        run_command(
            [RCLONE_BIN, "--config", str(config_path), "purge", version_full_path],
            logger,
            check=False,  # Don't fail if deletion fails
        )


def run_rclone_sync(
    source: Path,
    destination: str,
    config_path: Path,
    transfers: int,
    checkers: int,
    dry_run: bool,
    verbose: bool,
    debug: bool,
    keep_versions: int,
    timestamp: str,
    logger: logging.Logger,
) -> None:
    """Run rclone sync from source to destination.

    If keep_versions > 0, uses --backup-dir to preserve changed/deleted files
    in a versioned subdirectory.
    """
    cmd = [
        RCLONE_BIN,
        "--config", str(config_path),
        "sync",
        str(source) + "/",  # Trailing slash to sync contents
        destination,
        "--transfers", str(transfers),
        "--checkers", str(checkers),
        "--contimeout", "60s",
        "--timeout", "300s",
        "--retries", "3",
        "--low-level-retries", "10",
        "--links",  # Preserve symlinks as .rclonelink files (Dropbox doesn't support symlinks)
        "--tpslimit", "12",  # Dropbox API rate limit (12 requests/sec)
        "--tpslimit-burst", "1",  # Minimal bursting to stay within limits
    ]

    # Add backup-dir for versioning if enabled
    if keep_versions > 0:
        backup_dir = f"{destination}/{VERSIONS_DIR}/{timestamp}"
        cmd.extend(["--backup-dir", backup_dir])
        logger.debug(f"Version backup directory: {backup_dir}")

    if dry_run:
        cmd.append("--dry-run")

    if debug:
        cmd.extend(["--verbose", "--verbose"])
    elif verbose:
        cmd.append("--verbose")

    action = "Dry run" if dry_run else "Syncing"
    logger.info(f"{action}: {source} -> {destination}")
    logger.debug(f"Transfers: {transfers}, Checkers: {checkers}")

    # Check for termination before starting long-running operation
    check_termination()

    # Use Popen to stream output while also capturing for error handling
    global _active_child_process
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    _active_child_process = process

    try:
        # Use deque to limit memory usage - only keep last 20 lines for error context
        output_lines: deque[str] = deque(maxlen=20)
        assert process.stdout is not None, "stdout should not be None with PIPE"
        for line in process.stdout:
            line = line.rstrip()
            output_lines.append(line)
            if verbose or debug:
                print(line, file=sys.stderr)

        process.wait()
    finally:
        _active_child_process = None

    # Check if we were terminated
    if _terminate_requested:
        raise TerminatedError("Termination requested by signal")

    if process.returncode != 0:
        # Include last few lines of output in error message (deque already limits to 20)
        error_context = "\n".join(output_lines) if output_lines else "(no output)"
        raise DropboxPushError(
            f"rclone sync failed with exit code {process.returncode}\n"
            f"Last output:\n{error_context}"
        )

    logger.info("Sync completed successfully")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Sync ZFS dataset to cloud storage via rclone with snapshot support.",
        epilog="""
Examples:
  %(prog)s apps/config dropbox:TrueNAS-Backup/apps-config
  %(prog)s apps/data dropbox:Backup/data --dry-run -v
  %(prog)s tank/media remote:Backup --transfers 8 --keep-versions 5
  %(prog)s apps/config dropbox:Backup --rclone-config /path/to/rclone.conf
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "dataset",
        help="Source ZFS dataset (e.g., 'apps/config' or 'tank/data')",
    )
    parser.add_argument(
        "destination",
        help="rclone destination (e.g., 'dropbox:TrueNAS-Backup/apps-config')",
    )

    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Perform a trial run with no changes made (note: still creates/destroys local snapshots and clones)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output (implies --verbose)",
    )
    parser.add_argument(
        "--transfers",
        type=int,
        default=DEFAULT_TRANSFERS,
        metavar="N",
        help=f"Number of file transfers to run in parallel (default: {DEFAULT_TRANSFERS})",
    )
    parser.add_argument(
        "--keep-versions",
        type=int,
        default=0,
        metavar="N",
        help="Keep N previous versions in .versions/ subdirectory (default: 0 = no versioning)",
    )
    parser.add_argument(
        "--keep-snapshot",
        action="store_true",
        help="Keep the snapshot after sync (useful for debugging)",
    )
    parser.add_argument(
        "--keep-clone",
        action="store_true",
        help="Keep the clone tree after sync (useful for debugging)",
    )
    parser.add_argument(
        "--rclone-config",
        type=Path,
        default=get_default_rclone_config(),
        metavar="PATH",
        help=f"Path to rclone config file (default: {RCLONE_CONFIG_FILENAME} in script directory)",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    # Register signal handlers to ensure cleanup on termination
    signal.signal(signal.SIGTERM, _handle_termination_signal)
    signal.signal(signal.SIGHUP, _handle_termination_signal)

    args = parse_args()

    verbose = args.verbose or args.debug
    logger = setup_logging(verbose=verbose, debug=args.debug)

    # Calculate checkers (2x transfers, capped at 64)
    checkers = min(args.transfers * 2, 64)

    # Generate timestamp for this run
    timestamp = generate_timestamp()
    snapshot_name = f"{SNAPSHOT_PREFIX}-{timestamp}"

    # State tracking for cleanup
    snapshot_created = False
    clone_creation_started = False  # True once we begin creating clones (even if partial)
    clone_root: str | None = None

    try:
        # Acquire lock to prevent concurrent runs
        with LockFile(args.dataset, logger):
            cleanup_failed = False
            try:
                # Validate inputs
                validate_dataset_name(args.dataset, logger)
                validate_rclone_config(args.rclone_config, logger)
                root_mountpoint = validate_dataset(args.dataset, logger)
                validate_rclone_remote(args.destination, args.rclone_config, logger)

                # Enumerate all datasets
                datasets = list_datasets_recursive(args.dataset, logger)
                logger.info(f"Found {len(datasets)} dataset(s) to sync")

                # Calculate clone locations
                clone_root = get_clone_dataset_name(args.dataset)
                clone_mountpoint = get_clone_mountpoint(root_mountpoint)

                # Get pool altroot (TrueNAS sets altroot=/mnt, which affects mountpoint handling)
                pool_name = get_pool_name(args.dataset)
                altroot = get_pool_altroot(pool_name, logger)

                # Check if clone root already exists (leftover from failed run)
                check_result = run_command(
                    ["zfs", "list", "-H", clone_root],
                    logger,
                    check=False,
                )
                if check_result.returncode == 0:
                    # Verify it's actually our clone before destroying
                    if is_our_clone(clone_root, logger):
                        logger.warning(f"Stale clone tree found, cleaning up: {clone_root}")
                        destroy_clone_tree(clone_root, logger)
                    else:
                        raise DropboxPushError(
                            f"Dataset '{clone_root}' exists but is not a clone from this script.\n"
                            f"Please remove it manually or choose a different dataset name."
                        )

                # Create snapshot
                create_recursive_snapshot(args.dataset, snapshot_name, logger)
                snapshot_created = True

                # Create clone tree
                clone_creation_started = True  # Mark before starting so cleanup runs on partial failure
                create_clone_tree(
                    args.dataset,
                    datasets,
                    snapshot_name,
                    clone_root,
                    clone_mountpoint,
                    altroot,
                    logger,
                )

                # Verify clone mountpoint is accessible
                if not clone_mountpoint.exists():
                    raise DropboxPushError(f"Clone mountpoint not accessible: {clone_mountpoint}")

                # Run sync
                run_rclone_sync(
                    source=clone_mountpoint,
                    destination=args.destination,
                    config_path=args.rclone_config,
                    transfers=args.transfers,
                    checkers=checkers,
                    dry_run=args.dry_run,
                    verbose=verbose,
                    debug=args.debug,
                    keep_versions=args.keep_versions,
                    timestamp=timestamp,
                    logger=logger,
                )

                # Cleanup old versions
                if args.keep_versions > 0 and not args.dry_run:
                    cleanup_old_versions(
                        args.destination,
                        args.keep_versions,
                        args.rclone_config,
                        args.dry_run,
                        logger,
                    )

            finally:
                # Cleanup runs inside lock to prevent race conditions
                # Cleanup clone tree (even if partially created)
                if clone_creation_started and clone_root and not args.keep_clone:
                    try:
                        # Re-validate ownership before destroying to guard against race conditions
                        # (another process could have created a dataset with this name)
                        if is_our_clone(clone_root, logger):
                            destroy_clone_tree(clone_root, logger)
                        else:
                            logger.warning(
                                f"Clone root '{clone_root}' exists but is not ours - skipping cleanup"
                            )
                            cleanup_failed = True
                    except Exception as e:
                        logger.warning(f"Failed to cleanup clone tree: {e}")
                        cleanup_failed = True

                # Cleanup snapshot
                if snapshot_created and not args.keep_snapshot:
                    try:
                        destroy_recursive_snapshot(args.dataset, snapshot_name, logger)
                    except Exception as e:
                        logger.warning(f"Failed to cleanup snapshot: {e}")
                        cleanup_failed = True

        if cleanup_failed:
            logger.error("Sync succeeded but cleanup failed - manual cleanup may be required")
            sys.exit(2)
        sys.exit(0)

    except DropboxPushError as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

    except KeyboardInterrupt:
        logger.error("Interrupted by user")
        sys.exit(130)

    except TerminatedError as e:
        logger.error(f"Terminated: {e}")
        sys.exit(143)  # 128 + 15 (SIGTERM)

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
