"""
Push orchestrator for cloud-mirror.

This module provides the PushOrchestrator class that coordinates the complete
push workflow using dependency injection for testability.

Workflow steps:
1. Validate dataset exists
2. Validate rclone config and remote
3. List datasets recursively
4. Create recursive snapshot
5. Create clone tree
6. Run rclone sync
7. Cleanup old versions (if keep_versions > 0)
8. Destroy clone tree (unless keep_clone)
9. Destroy snapshot (unless keep_snapshot)
"""

from __future__ import annotations

import fcntl
import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Generator, Protocol

if TYPE_CHECKING:
    from typing import IO

# =============================================================================
# Exceptions
# =============================================================================


class PushError(Exception):
    """Base exception for push failures."""


class ValidationError(PushError):
    """Dataset or remote validation failed."""


class SnapshotError(PushError):
    """Snapshot creation/destruction failed."""


class CloneError(PushError):
    """Clone tree creation/destruction failed."""


class SyncError(PushError):
    """Rclone sync failed."""


class LockError(PushError):
    """Could not acquire lock (concurrent operation)."""

    def __init__(self, pool: str, lock_path: Path) -> None:
        """Initialize LockError with pool name and lock file path.

        Args:
            pool: Name of the ZFS pool that is locked.
            lock_path: Path to the lock file.
        """
        super().__init__(
            f"Could not acquire lock for pool '{pool}': "
            f"another operation may be in progress. Lock file: {lock_path}"
        )
        self.pool = pool
        self.lock_path = lock_path


# =============================================================================
# Locking
# =============================================================================


def get_lock_directory() -> Path:
    """Get the directory for lock files.

    Returns the lock directory following XDG conventions:
    1. $XDG_RUNTIME_DIR/cloud-mirror if XDG_RUNTIME_DIR is set
    2. /var/run/cloud-mirror if it exists and is writable
    3. ~/.cache/cloud-mirror as fallback

    Returns:
        Path to the lock directory (created if necessary).
    """
    # Try XDG_RUNTIME_DIR first (e.g., /run/user/1000 on Linux)
    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
    if xdg_runtime:
        lock_dir = Path(xdg_runtime) / "cloud-mirror"
        try:
            lock_dir.mkdir(parents=True, exist_ok=True)
            return lock_dir
        except OSError:
            pass  # Fall through to next option

    # Try /var/run/cloud-mirror (system-wide, requires privileges)
    var_run = Path("/var/run/cloud-mirror")
    try:
        var_run.mkdir(parents=True, exist_ok=True)
        return var_run
    except OSError:
        pass  # Fall through to user cache

    # Fallback to user cache directory
    cache_dir = Path.home() / ".cache" / "cloud-mirror"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def extract_pool_name(dataset: str) -> str:
    """Extract the pool name from a dataset path.

    Args:
        dataset: Dataset name (e.g., "testpool/data/subdir").

    Returns:
        Pool name (e.g., "testpool").
    """
    return dataset.split("/")[0]


@contextmanager
def pool_lock(
    dataset: str,
    lock_dir: Path | None = None,
) -> Generator[Path, None, None]:
    """Context manager for acquiring an exclusive lock on a ZFS pool.

    Acquires a non-blocking exclusive lock using fcntl.flock(LOCK_EX | LOCK_NB).
    The lock is per-pool (not per-dataset) to prevent conflicting operations.

    Args:
        dataset: Dataset name to extract pool from (e.g., "testpool/data").
        lock_dir: Optional lock directory override (for testing).

    Yields:
        Path to the lock file.

    Raises:
        LockError: If lock cannot be acquired (another operation in progress).

    Example:
        with pool_lock("testpool/data") as lock_path:
            # Exclusive access to testpool
            run_sync()
        # Lock automatically released
    """
    pool = extract_pool_name(dataset)
    lock_directory = lock_dir or get_lock_directory()
    lock_path = lock_directory / f"{pool}.lock"

    # Ensure lock directory exists
    lock_directory.mkdir(parents=True, exist_ok=True)

    # Open lock file (create if doesn't exist)
    lock_file: IO[str] | None = None
    try:
        lock_file = lock_path.open("w")

        # Try to acquire exclusive lock (non-blocking)
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as err:
            # Lock is held by another process
            raise LockError(pool, lock_path) from err

        # Write PID to lock file for debugging
        lock_file.write(f"{os.getpid()}\n")
        lock_file.flush()

        yield lock_path

    finally:
        if lock_file is not None:
            # Release lock and close file
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass  # Ignore errors during unlock
            lock_file.close()


# =============================================================================
# Configuration and Result Types
# =============================================================================


@dataclass(frozen=True)
class PushConfig:
    """Configuration for push operation.

    Attributes:
        dataset: ZFS dataset to push (e.g., "pool/data").
        destination: rclone destination (e.g., "dropbox:backup").
        config_path: Path to rclone configuration file.
        transfers: Number of parallel transfers.
        tpslimit: Transactions per second limit.
        dry_run: If True, perform a trial run with no changes.
        keep_versions: Number of old versions to keep (0 = no versioning).
        keep_clone: If True, keep clone tree after sync.
        keep_snapshot: If True, keep snapshot after sync.
    """

    dataset: str
    destination: str
    config_path: Path
    transfers: int = 64
    tpslimit: int = 12
    dry_run: bool = False
    keep_versions: int = 0
    keep_clone: bool = False
    keep_snapshot: bool = False


@dataclass(frozen=True)
class PushResult:
    """Result of a push operation.

    Attributes:
        success: True if push completed without errors.
        files_transferred: Number of files transferred.
        snapshot_name: Name of the snapshot created.
        clone_path: Path to the clone tree (if kept).
        versions_deleted: Number of old versions deleted.
    """

    success: bool
    files_transferred: int = 0
    snapshot_name: str = ""
    clone_path: Path | None = None
    versions_deleted: int = 0


# =============================================================================
# Operations Protocol
# =============================================================================


class PushOperations(Protocol):
    """Protocol defining operations required for push workflow.

    This protocol enables dependency injection for testing.
    Any class implementing these methods can be used with PushOrchestrator.
    """

    def validate_dataset(self, dataset: str) -> None:
        """Validate that a ZFS dataset exists.

        Args:
            dataset: Dataset name to validate.

        Raises:
            ValidationError: If dataset does not exist.
        """
        ...

    def validate_remote(self, remote: str, config_path: Path) -> None:
        """Validate rclone remote configuration.

        Args:
            remote: Remote destination (e.g., "dropbox:backup").
            config_path: Path to rclone configuration file.

        Raises:
            ValidationError: If remote is not configured or invalid.
        """
        ...

    def list_datasets(self, root_dataset: str) -> list[str]:
        """List all datasets under and including the root dataset.

        Args:
            root_dataset: Root dataset name.

        Returns:
            List of dataset names, sorted (parent before children).
        """
        ...

    def create_snapshot(self, root_dataset: str, snapshot_name: str) -> None:
        """Create a recursive ZFS snapshot.

        Args:
            root_dataset: Root dataset name.
            snapshot_name: Name for the snapshot (without @).

        Raises:
            SnapshotError: If snapshot creation fails.
        """
        ...

    def create_clone_tree(
        self,
        root_dataset: str,
        datasets: list[str],
        snapshot_name: str,
    ) -> Path:
        """Create clone tree from snapshot.

        Args:
            root_dataset: Root dataset name.
            datasets: List of all datasets to clone.
            snapshot_name: Name of the snapshot to clone from.

        Returns:
            Path to the mounted clone tree root.

        Raises:
            CloneError: If clone creation fails.
        """
        ...

    def sync(
        self,
        source: Path,
        destination: str,
        config_path: Path,
        transfers: int,
        tpslimit: int,
        dry_run: bool,
        keep_versions: int,
        timestamp: str,
    ) -> int:
        """Run rclone sync operation.

        Args:
            source: Source path to sync from.
            destination: rclone destination.
            config_path: Path to rclone configuration file.
            transfers: Number of parallel transfers.
            tpslimit: Transactions per second limit.
            dry_run: If True, perform trial run.
            keep_versions: Number of versions to keep (for backup-dir).
            timestamp: Timestamp for version directory.

        Returns:
            Number of files transferred.

        Raises:
            SyncError: If sync fails.
        """
        ...

    def cleanup_versions(
        self,
        destination: str,
        config_path: Path,
        keep_versions: int,
    ) -> int:
        """Cleanup old version directories.

        Args:
            destination: rclone destination.
            config_path: Path to rclone configuration file.
            keep_versions: Number of versions to keep.

        Returns:
            Number of versions deleted.
        """
        ...

    def destroy_clone_tree(self, root_dataset: str) -> None:
        """Destroy the clone tree.

        Args:
            root_dataset: Root dataset name (clone name derived from this).
        """
        ...

    def destroy_snapshot(self, root_dataset: str, snapshot_name: str) -> None:
        """Destroy recursive snapshot.

        Args:
            root_dataset: Root dataset name.
            snapshot_name: Name of the snapshot (without @).
        """
        ...


# =============================================================================
# Orchestrator
# =============================================================================


class PushOrchestrator:
    """Orchestrates the push workflow using injected operations.

    The orchestrator coordinates the 9-step push workflow:
    1. Validate dataset exists
    2. Validate rclone config and remote
    3. List datasets recursively
    4. Create recursive snapshot
    5. Create clone tree
    6. Run rclone sync
    7. Cleanup old versions (if keep_versions > 0)
    8. Destroy clone tree (unless keep_clone)
    9. Destroy snapshot (unless keep_snapshot)

    Cleanup (steps 8-9) always occurs via try/finally, unless keep flags are set.
    """

    def __init__(
        self,
        operations: PushOperations,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize orchestrator with operations implementation.

        Args:
            operations: Implementation of PushOperations protocol.
            logger: Logger for diagnostics.
        """
        self._ops = operations
        self._logger = logger or logging.getLogger(__name__)

    def run(self, config: PushConfig) -> PushResult:
        """Execute the push workflow.

        Args:
            config: Push configuration.

        Returns:
            PushResult with success status and details.

        Raises:
            ValidationError: If dataset or remote validation fails.
            SnapshotError: If snapshot operations fail.
            CloneError: If clone operations fail.
            SyncError: If rclone sync fails.
        """
        # Generate timestamp for snapshot and version backup
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        snapshot_name = f"cloudmirror-{timestamp}"

        # Track what resources were created for cleanup
        snapshot_created = False
        clone_created = False
        clone_path: Path | None = None
        files_transferred = 0
        versions_deleted = 0

        try:
            # Step 1: Validate dataset exists
            self._logger.debug(f"Validating dataset: {config.dataset}")
            self._ops.validate_dataset(config.dataset)

            # Step 2: Validate rclone config and remote
            self._logger.debug(f"Validating remote: {config.destination}")
            self._ops.validate_remote(config.destination, config.config_path)

            # Step 3: List datasets recursively
            self._logger.debug(f"Listing datasets under: {config.dataset}")
            datasets = self._ops.list_datasets(config.dataset)

            # Step 4: Create recursive snapshot
            self._logger.info(f"Creating snapshot: {config.dataset}@{snapshot_name}")
            self._ops.create_snapshot(config.dataset, snapshot_name)
            snapshot_created = True

            # Step 5: Create clone tree
            self._logger.info("Creating clone tree")
            clone_path = self._ops.create_clone_tree(
                config.dataset, datasets, snapshot_name
            )
            clone_created = True

            # Step 6: Run rclone sync
            self._logger.info(f"Syncing to {config.destination}")
            files_transferred = self._ops.sync(
                source=clone_path,
                destination=config.destination,
                config_path=config.config_path,
                transfers=config.transfers,
                tpslimit=config.tpslimit,
                dry_run=config.dry_run,
                keep_versions=config.keep_versions,
                timestamp=timestamp,
            )

            # Step 7: Cleanup old versions (if enabled)
            if config.keep_versions > 0:
                self._logger.info(f"Cleaning up old versions (keeping {config.keep_versions})")
                versions_deleted = self._ops.cleanup_versions(
                    config.destination,
                    config.config_path,
                    config.keep_versions,
                )

        finally:
            # Step 8: Destroy clone tree (unless keep_clone)
            if clone_created and not config.keep_clone:
                self._logger.info("Destroying clone tree")
                try:
                    self._ops.destroy_clone_tree(config.dataset)
                except Exception as e:
                    self._logger.warning(f"Failed to destroy clone tree: {e}")

            # Step 9: Destroy snapshot (unless keep_snapshot)
            if snapshot_created and not config.keep_snapshot:
                self._logger.info(f"Destroying snapshot: {config.dataset}@{snapshot_name}")
                try:
                    self._ops.destroy_snapshot(config.dataset, snapshot_name)
                except Exception as e:
                    self._logger.warning(f"Failed to destroy snapshot: {e}")

        return PushResult(
            success=True,
            files_transferred=files_transferred,
            snapshot_name=snapshot_name if config.keep_snapshot else "",
            clone_path=clone_path if config.keep_clone else None,
            versions_deleted=versions_deleted,
        )
