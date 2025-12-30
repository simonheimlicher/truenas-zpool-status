"""
ZFS operations for cloud-mirror.

This module provides functions for ZFS snapshot and dataset operations.
In development (macOS), commands run via Colima VM.
In production (TrueNAS), commands run directly.
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Callable

# Timeouts (seconds)
TIMEOUT_ZFS_QUICK = 60
TIMEOUT_ZFS_RECURSIVE = 1800

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
        result = subprocess.run(
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
        result = subprocess.run(
            ["colima", "ssh", "--profile", _VM_PROFILE, "--", "bash", "-c", cmd_str],
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
            f"{', '.join(stale_snapshots[:3])}{'...' if len(stale_snapshots) > 3 else ''}"
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
