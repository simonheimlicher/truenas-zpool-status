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


# =============================================================================
# Real Operations Implementation
# =============================================================================


class RealPushOperations:
    """Real implementation of PushOperations using ZFS and rclone.

    This class wraps the actual ZFS and rclone operations from zfs.py
    and rclone.py modules, providing the concrete implementation for
    the PushOperations protocol.
    """

    def __init__(self, logger: logging.Logger) -> None:
        """Initialize with logger.

        Args:
            logger: Logger for operation diagnostics.
        """
        self._logger = logger
        self._altroot: Path | None = None  # Cached pool altroot

    def validate_dataset(self, dataset: str) -> None:
        """Validate that a ZFS dataset exists.

        Args:
            dataset: Dataset name to validate.

        Raises:
            ValidationError: If dataset does not exist.
        """
        from cloud_mirror.zfs import ZfsError, run_zfs_command

        try:
            run_zfs_command(["zfs", "list", "-H", dataset], self._logger)
        except ZfsError as e:
            raise ValidationError(f"Dataset '{dataset}' does not exist: {e}") from e

    def validate_remote(self, remote: str, config_path: Path) -> None:
        """Validate rclone remote configuration.

        Args:
            remote: Remote destination (e.g., "dropbox:backup").
            config_path: Path to rclone configuration file.

        Raises:
            ValidationError: If remote is not configured or invalid.
        """
        import shutil
        import subprocess

        # Extract remote name from "remotename:path"
        remote_name = remote.split(":")[0]

        # Find rclone binary
        rclone_bin = shutil.which("rclone") or "/usr/bin/rclone"

        try:
            result = subprocess.run(  # noqa: S603, S607
                [rclone_bin, "--config", str(config_path), "listremotes"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise ValidationError(
                    f"Failed to list rclone remotes: {result.stderr}"
                )

            remotes = [r.rstrip(":") for r in result.stdout.strip().split("\n") if r]
            if remote_name not in remotes:
                raise ValidationError(
                    f"Remote '{remote_name}' not found in rclone config. "
                    f"Available remotes: {', '.join(remotes)}"
                )
        except subprocess.TimeoutExpired as e:
            raise ValidationError(f"Timeout validating rclone remote: {e}") from e
        except FileNotFoundError as e:
            raise ValidationError(f"rclone not found: {e}") from e

    def list_datasets(self, root_dataset: str) -> list[str]:
        """List all datasets under and including the root dataset.

        Args:
            root_dataset: Root dataset name.

        Returns:
            List of dataset names, sorted (parent before children).
        """
        from cloud_mirror.zfs import list_datasets_recursive

        return list_datasets_recursive(root_dataset, self._logger)

    def create_snapshot(self, root_dataset: str, snapshot_name: str) -> None:
        """Create a recursive ZFS snapshot.

        Args:
            root_dataset: Root dataset name.
            snapshot_name: Name for the snapshot (without @).

        Raises:
            SnapshotError: If snapshot creation fails.
        """
        from cloud_mirror.zfs import ZfsError, create_recursive_snapshot

        try:
            create_recursive_snapshot(root_dataset, snapshot_name, self._logger)
        except ZfsError as e:
            raise SnapshotError(f"Failed to create snapshot: {e}") from e

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
        from cloud_mirror.zfs import (
            ZfsError,
            create_clone_tree,
            destroy_clone_tree,
            find_stale_clone,
            get_clone_dataset_name,
            get_clone_mountpoint,
            get_pool_altroot,
            get_pool_name,
            run_zfs_command,
        )

        # Get source mountpoint
        result = run_zfs_command(
            ["zfs", "get", "-H", "-o", "value", "mountpoint", root_dataset],
            self._logger,
        )
        source_mountpoint = Path(result.stdout.strip())

        # Derive clone names
        clone_root = get_clone_dataset_name(root_dataset)
        clone_mountpoint = get_clone_mountpoint(source_mountpoint)

        # Get pool altroot for TrueNAS compatibility
        pool = get_pool_name(root_dataset)
        self._altroot = get_pool_altroot(pool, self._logger)

        # Clean up stale clones if any
        stale_clone = find_stale_clone(root_dataset, self._logger)
        if stale_clone:
            self._logger.warning(f"Found stale clone, destroying: {stale_clone}")
            try:
                destroy_clone_tree(stale_clone, self._logger)
            except ZfsError as e:
                raise CloneError(f"Failed to clean stale clone: {e}") from e

        # Create clone tree
        try:
            create_clone_tree(
                root_dataset,
                datasets,
                snapshot_name,
                clone_root,
                clone_mountpoint,
                self._altroot,
                self._logger,
            )
        except ZfsError as e:
            raise CloneError(f"Failed to create clone tree: {e}") from e

        return clone_mountpoint

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
        from cloud_mirror.rclone import RcloneSyncConfig, RcloneSyncError, run_rclone_sync

        config = RcloneSyncConfig(
            source=source,
            destination=destination,
            config_path=config_path,
            transfers=transfers,
            tpslimit=tpslimit,
            dry_run=dry_run,
            keep_versions=keep_versions,
            timestamp=timestamp,
        )

        try:
            result = run_rclone_sync(config, logger=self._logger)
            return result.files_transferred
        except RcloneSyncError as e:
            raise SyncError(f"Sync failed: {e}") from e

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
        from cloud_mirror.rclone import cleanup_old_versions

        result = cleanup_old_versions(
            destination,
            config_path,
            keep_versions,
            logger=self._logger,
        )
        return result.deleted_count

    def destroy_clone_tree(self, root_dataset: str) -> None:
        """Destroy the clone tree.

        Args:
            root_dataset: Root dataset name (clone name derived from this).
        """
        from cloud_mirror.zfs import destroy_clone_tree, get_clone_dataset_name

        clone_root = get_clone_dataset_name(root_dataset)
        destroy_clone_tree(clone_root, self._logger)

    def destroy_snapshot(self, root_dataset: str, snapshot_name: str) -> None:
        """Destroy recursive snapshot.

        Args:
            root_dataset: Root dataset name.
            snapshot_name: Name of the snapshot (without @).
        """
        from cloud_mirror.zfs import destroy_recursive_snapshot

        destroy_recursive_snapshot(root_dataset, snapshot_name, self._logger)


# =============================================================================
# Main Entry Point
# =============================================================================


def run_push(
    dataset: str,
    destination: str,
    config_path: Path | None = None,
    transfers: int = 64,
    tpslimit: int = 12,
    dry_run: bool = False,
    keep_versions: int = 0,
    keep_clone: bool = False,
    keep_snapshot: bool = False,
    verbose: int = 0,
) -> int:
    """Execute a push operation with locking and error handling.

    This is the main entry point for the push command. It:
    1. Acquires a per-pool lock
    2. Creates RealPushOperations
    3. Runs PushOrchestrator
    4. Handles errors with user-friendly messages

    Args:
        dataset: ZFS dataset to push.
        destination: rclone destination (e.g., "dropbox:backup").
        config_path: Path to rclone config, or None for default.
        transfers: Number of parallel transfers.
        tpslimit: Transactions per second limit.
        dry_run: If True, perform trial run.
        keep_versions: Number of old versions to keep.
        keep_clone: If True, keep clone tree after sync.
        keep_snapshot: If True, keep snapshot after sync.
        verbose: Verbosity level (0=quiet, 1=info, 2=debug).

    Returns:
        Exit code: 0 for success, 1 for failure.
    """
    import sys

    # Setup logging based on verbose level
    log_level = logging.WARNING
    if verbose >= 2:
        log_level = logging.DEBUG
    elif verbose >= 1:
        log_level = logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    logger = logging.getLogger("cloud-mirror")
    logger.setLevel(log_level)

    # Resolve config path
    if config_path is None:
        config_path = Path.home() / ".config" / "rclone" / "rclone.conf"

    try:
        with pool_lock(dataset):
            logger.info(f"Starting push: {dataset} -> {destination}")

            # Create real operations and orchestrator
            operations = RealPushOperations(logger)
            orchestrator = PushOrchestrator(operations, logger)

            # Build config
            config = PushConfig(
                dataset=dataset,
                destination=destination,
                config_path=config_path,
                transfers=transfers,
                tpslimit=tpslimit,
                dry_run=dry_run,
                keep_versions=keep_versions,
                keep_clone=keep_clone,
                keep_snapshot=keep_snapshot,
            )

            # Run push
            result = orchestrator.run(config)

            if result.success:
                logger.info(
                    f"Push complete: {result.files_transferred} files transferred"
                )
                return 0
            else:
                return 1

    except LockError as e:
        print(f"Error: {e}", file=sys.stderr)  # noqa: T201
        print("Suggestion: Wait for the other operation to complete.", file=sys.stderr)  # noqa: T201
        return 1

    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)  # noqa: T201
        print("Suggestion: Check that the dataset exists and rclone is configured.", file=sys.stderr)  # noqa: T201
        return 1

    except SnapshotError as e:
        print(f"Error: {e}", file=sys.stderr)  # noqa: T201
        print("Suggestion: Check ZFS permissions and disk space.", file=sys.stderr)  # noqa: T201
        return 1

    except CloneError as e:
        print(f"Error: {e}", file=sys.stderr)  # noqa: T201
        print("Suggestion: Check for existing clones and ZFS permissions.", file=sys.stderr)  # noqa: T201
        return 1

    except SyncError as e:
        print(f"Error: {e}", file=sys.stderr)  # noqa: T201
        print("Suggestion: Check network connectivity and rclone configuration.", file=sys.stderr)  # noqa: T201
        return 1

    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)  # noqa: T201
        return 130  # Standard exit code for SIGINT

    except Exception as e:
        logger.exception("Unexpected error")
        print(f"Error: Unexpected error: {e}", file=sys.stderr)  # noqa: T201
        return 1
