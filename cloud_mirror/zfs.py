"""
ZFS operations for cloud-mirror.

This module provides functions for ZFS snapshot, dataset, and clone operations.
In development (macOS), commands run via Colima VM.
In production (TrueNAS), commands run directly.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Callable

# Timeouts (seconds)
TIMEOUT_ZFS_QUICK = 60
TIMEOUT_ZFS_RECURSIVE = 1800

# Logging limits
_MAX_SNAPSHOTS_IN_LOG = 3

# Clone tree constants
CLONE_SUFFIX = ".cloudmirror"
ZFS_MANAGED_PROPERTY = "ch.srvr.cloudmirror:managed"
ZFS_MANAGED_VALUE = "true"

# Environment detection
_USE_VM = os.environ.get("CLOUD_MIRROR_USE_VM", "").lower() in ("1", "true", "yes")
_VM_PROFILE = os.environ.get("CLOUD_MIRROR_VM_PROFILE", "zfs-test")


class ZfsError(Exception):
    """ZFS operation failed."""


def _run_command_local(
    cmd: list[str],
    logger: logging.Logger,
    check: bool = True,
    timeout: int = TIMEOUT_ZFS_QUICK,
) -> subprocess.CompletedProcess[str]:
    """Run command directly (production mode)."""
    logger.debug(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(  # noqa: S603 - CLI tool, cmd built from trusted internal code
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if check and result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else f"Exit code {result.returncode}"
            raise ZfsError(f"Command failed: {' '.join(cmd)}: {error_msg}")
        return result
    except subprocess.TimeoutExpired as e:
        raise ZfsError(f"Command timed out after {timeout}s: {' '.join(cmd)}") from e


def _run_command_vm(
    cmd: list[str],
    logger: logging.Logger,
    check: bool = True,
    timeout: int = TIMEOUT_ZFS_QUICK,
) -> subprocess.CompletedProcess[str]:
    """Run command in Colima VM (development mode)."""
    # Prefix with sudo for ZFS commands
    cmd_str = " ".join(cmd)
    if cmd[0] in ("zfs", "zpool"):
        cmd_str = f"sudo {cmd_str}"

    logger.debug(f"Running in VM: {cmd_str}")
    try:
        result = subprocess.run(  # noqa: S603 - CLI tool, cmd built from trusted internal code
            ["colima", "ssh", "--profile", _VM_PROFILE, "--", "bash", "-c", cmd_str],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if check and result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else f"Exit code {result.returncode}"
            raise ZfsError(f"Command failed: {cmd_str}: {error_msg}")
        return result
    except subprocess.TimeoutExpired as e:
        raise ZfsError(f"Command timed out after {timeout}s: {cmd_str}") from e


def _get_command_runner() -> Callable[..., subprocess.CompletedProcess[str]]:
    """Get the appropriate command runner based on environment."""
    if _USE_VM:
        return _run_command_vm
    return _run_command_local


def run_zfs_command(
    cmd: list[str],
    logger: logging.Logger,
    check: bool = True,
    timeout: int = TIMEOUT_ZFS_QUICK,
) -> subprocess.CompletedProcess[str]:
    """Run a ZFS command, using VM in development or direct in production."""
    runner = _get_command_runner()
    return runner(cmd, logger, check, timeout)


def list_datasets_recursive(root_dataset: str, logger: logging.Logger) -> list[str]:
    """List all datasets under and including the root dataset.

    Args:
        root_dataset: The root dataset name (e.g., "testpool/data")
        logger: Logger instance

    Returns:
        List of dataset names, sorted (parent before children)
    """
    logger.debug(f"Enumerating datasets under: {root_dataset}")

    result = run_zfs_command(
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
    result = run_zfs_command(
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
        if "@" in line and line.split("@")[1] == snapshot_name:
            stale.append(line)

    return stale


def destroy_stale_snapshots(
    root_dataset: str,
    snapshot_name: str,
    stale_snapshots: list[str],
    logger: logging.Logger,
) -> None:
    """Destroy stale snapshots, handling the case where only children exist."""
    full_snapshot = f"{root_dataset}@{snapshot_name}"
    root_exists = full_snapshot in stale_snapshots

    if root_exists:
        result = run_zfs_command(
            ["zfs", "destroy", "-r", full_snapshot],
            logger,
            check=False,
            timeout=TIMEOUT_ZFS_RECURSIVE,
        )
        if result.returncode == 0:
            return
        logger.debug("Recursive destroy failed, falling back to individual destruction")

    # Destroy in reverse order (children before parents)
    for snap in sorted(stale_snapshots, reverse=True):
        result = run_zfs_command(
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
    """Create a recursive ZFS snapshot.

    Automatically detects and cleans up stale snapshots before creating.

    Args:
        root_dataset: The root dataset name
        snapshot_name: The snapshot name (without @)
        logger: Logger instance

    Raises:
        ZfsError: If snapshot creation fails
    """
    full_snapshot = f"{root_dataset}@{snapshot_name}"

    # Check for and clean stale snapshots
    stale_snapshots = find_stale_snapshots(root_dataset, snapshot_name, logger)
    if stale_snapshots:
        logger.warning(
            f"Found {len(stale_snapshots)} stale snapshot(s), destroying: "
            f"{', '.join(stale_snapshots[:_MAX_SNAPSHOTS_IN_LOG])}"
            f"{'...' if len(stale_snapshots) > _MAX_SNAPSHOTS_IN_LOG else ''}"
        )
        destroy_stale_snapshots(root_dataset, snapshot_name, stale_snapshots, logger)

    logger.info(f"Creating recursive snapshot: {full_snapshot}")
    run_zfs_command(
        ["zfs", "snapshot", "-r", full_snapshot],
        logger,
        timeout=TIMEOUT_ZFS_RECURSIVE,
    )


def destroy_recursive_snapshot(
    root_dataset: str,
    snapshot_name: str,
    logger: logging.Logger,
) -> None:
    """Destroy a recursive ZFS snapshot.

    Does not raise an error if the snapshot doesn't exist.

    Args:
        root_dataset: The root dataset name
        snapshot_name: The snapshot name (without @)
        logger: Logger instance
    """
    full_snapshot = f"{root_dataset}@{snapshot_name}"
    logger.info(f"Destroying recursive snapshot: {full_snapshot}")

    result = run_zfs_command(
        ["zfs", "destroy", "-r", full_snapshot],
        logger,
        check=False,
        timeout=TIMEOUT_ZFS_RECURSIVE,
    )

    if result.returncode != 0:
        logger.warning(f"Failed to destroy snapshot (may not exist): {full_snapshot}")


# =============================================================================
# Clone Tree Operations
# =============================================================================


def get_clone_dataset_name(root_dataset: str) -> str:
    """Derive the clone root dataset name from the source dataset.

    Args:
        root_dataset: The source dataset name (e.g., "testpool/data")

    Returns:
        Clone dataset name (e.g., "testpool/data.cloudmirror")
    """
    return f"{root_dataset}{CLONE_SUFFIX}"


def get_clone_mountpoint(root_mountpoint: Path) -> Path:
    """Derive the clone mountpoint from the source mountpoint.

    Args:
        root_mountpoint: The source mountpoint (e.g., Path("/testpool/data"))

    Returns:
        Clone mountpoint (e.g., Path("/testpool/data.cloudmirror"))
    """
    return root_mountpoint.parent / f"{root_mountpoint.name}{CLONE_SUFFIX}"


def get_pool_name(dataset: str) -> str:
    """Extract the pool name from a dataset name.

    Args:
        dataset: Full dataset name (e.g., "testpool/data/child")

    Returns:
        Pool name (e.g., "testpool")
    """
    return dataset.split("/")[0]


def get_pool_altroot(pool: str, logger: logging.Logger) -> Path | None:
    """Get the altroot property of a ZFS pool.

    TrueNAS SCALE sets altroot=/mnt on pools. When setting mountpoints,
    ZFS prepends the altroot, so we need to strip it from our paths.

    Args:
        pool: Pool name
        logger: Logger instance

    Returns:
        Path to altroot if set, None if not set or on error.
    """
    result = run_zfs_command(
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


def strip_altroot(mountpoint: Path, altroot: Path | None) -> Path:
    """Strip altroot prefix from a mountpoint for use with zfs clone -o mountpoint.

    When a pool has altroot set (e.g., /mnt on TrueNAS), ZFS prepends it to
    any mountpoint you specify. So to get /mnt/testpool/data.cloudmirror,
    you need to specify /testpool/data.cloudmirror.

    Args:
        mountpoint: The desired filesystem path (e.g., /mnt/testpool/data.cloudmirror)
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


def is_our_clone(dataset: str, logger: logging.Logger) -> bool:
    """Check if a dataset is a clone created by cloud-mirror.

    Checks for our ZFS user property (ch.srvr.cloudmirror:managed=true).

    Args:
        dataset: Dataset name to check
        logger: Logger instance

    Returns:
        True if the dataset has our management property, False otherwise.
    """
    result = run_zfs_command(
        ["zfs", "get", "-H", "-o", "value", ZFS_MANAGED_PROPERTY, dataset],
        logger,
        check=False,
    )

    if result.returncode != 0:
        return False

    prop_value = result.stdout.strip()
    return prop_value == ZFS_MANAGED_VALUE


def create_clone(
    snapshot: str,
    clone_dataset: str,
    mountpoint: Path,
    altroot: Path | None,
    logger: logging.Logger,
) -> None:
    """Create a clone from a snapshot with management property.

    Args:
        snapshot: Full snapshot name (e.g., "testpool/data@snap")
        clone_dataset: Name for the clone dataset
        mountpoint: Desired filesystem mountpoint
        altroot: Pool's altroot property (mountpoints are adjusted for this)
        logger: Logger instance

    Raises:
        ZfsError: If clone creation fails
    """
    # Adjust mountpoint for altroot
    zfs_mountpoint = strip_altroot(mountpoint, altroot)

    logger.debug(f"Cloning {snapshot} -> {clone_dataset} (mount: {mountpoint})")

    run_zfs_command(
        [
            "zfs", "clone",
            "-o", f"mountpoint={zfs_mountpoint}",
            "-o", "readonly=on",
            "-o", f"{ZFS_MANAGED_PROPERTY}={ZFS_MANAGED_VALUE}",
            snapshot,
            clone_dataset,
        ],
        logger,
    )


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

    Raises:
        ZfsError: If any clone creation fails
    """
    logger.info(f"Creating clone tree: {clone_root} -> {clone_mountpoint}")

    for dataset in datasets:
        # Calculate relative path from root dataset
        if dataset == root_dataset:
            relative = ""
        else:
            relative = dataset.removeprefix(root_dataset + "/")

        # Determine clone dataset name and mountpoint
        if relative:
            clone_dataset = f"{clone_root}/{relative}"
            clone_mp = clone_mountpoint / relative
        else:
            clone_dataset = clone_root
            clone_mp = clone_mountpoint

        snapshot_full = f"{dataset}@{snapshot_name}"

        create_clone(snapshot_full, clone_dataset, clone_mp, altroot, logger)

    logger.debug("Clone tree created successfully")

    # Check if root clone is mounted
    root_mount_check = run_zfs_command(
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
        if dataset == root_dataset:
            clone_dataset = clone_root
        else:
            relative = dataset.removeprefix(root_dataset + "/")
            clone_dataset = f"{clone_root}/{relative}"

        mount_result = run_zfs_command(
            ["zfs", "mount", clone_dataset],
            logger,
            check=False,
        )
        if mount_result.returncode != 0:
            logger.warning(f"Failed to mount clone: {clone_dataset}")


def find_stale_clone(root_dataset: str, logger: logging.Logger) -> str | None:
    """Find a stale clone tree from a previous failed run.

    Args:
        root_dataset: The source root dataset name
        logger: Logger instance

    Returns:
        Clone root name if a stale clone exists and is ours, None otherwise.
    """
    clone_root = get_clone_dataset_name(root_dataset)

    # Check if clone root exists
    result = run_zfs_command(
        ["zfs", "list", "-H", clone_root],
        logger,
        check=False,
    )

    if result.returncode != 0:
        # Clone doesn't exist
        return None

    # Verify it's our clone
    if is_our_clone(clone_root, logger):
        return clone_root

    return None


class CloneNotOursError(ZfsError):
    """Raised when attempting to destroy a clone that isn't managed by us."""

    def __init__(self, dataset: str) -> None:
        super().__init__(
            f"Dataset '{dataset}' exists but is not managed by cloud-mirror. "
            f"Missing property: {ZFS_MANAGED_PROPERTY}={ZFS_MANAGED_VALUE}"
        )
        self.dataset = dataset


def destroy_clone_tree(clone_root: str, logger: logging.Logger) -> None:
    """Destroy the entire clone tree recursively.

    Only destroys clones that have our management property.

    Args:
        clone_root: The clone root dataset name
        logger: Logger instance

    Raises:
        CloneNotOursError: If the clone exists but lacks our management property.
    """
    logger.info(f"Destroying clone tree: {clone_root}")

    # Check if it exists first
    check_result = run_zfs_command(
        ["zfs", "list", "-H", clone_root],
        logger,
        check=False,
    )

    if check_result.returncode != 0:
        logger.debug("Clone tree does not exist, nothing to destroy")
        return

    # Verify it's our clone before destroying
    if not is_our_clone(clone_root, logger):
        raise CloneNotOursError(clone_root)

    # Destroy recursively with force (handles unmount automatically)
    result = run_zfs_command(
        ["zfs", "destroy", "-rf", clone_root],
        logger,
        check=False,
        timeout=TIMEOUT_ZFS_RECURSIVE,
    )

    if result.returncode != 0:
        error_msg = result.stderr.strip() if result.stderr else "unknown error"
        logger.warning(f"Failed to destroy clone tree: {error_msg}")
        logger.warning(f"Manual cleanup required: sudo zfs destroy -rf {clone_root}")
    else:
        logger.debug("Clone tree destroyed successfully")
