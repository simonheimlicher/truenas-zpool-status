"""
Pull sync operations for cloud-mirror.

This module provides:
- Pre-pull snapshot creation for rollback safety
- rclone pull command building
- Pull workflow orchestration

The pull workflow:
1. Validate dataset and get mountpoint
2. Validate rclone remote configuration
3. Create pre-pull snapshot (for rollback safety)
4. Run rclone sync from remote to local
5. Destroy pre-pull snapshot (on success only)
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    pass


# Snapshot prefix for pre-pull snapshots
PRE_PULL_SNAPSHOT_PREFIX = "dropboxpull-pre"

# Default sync parameters
DEFAULT_TRANSFERS = 64
DEFAULT_TPSLIMIT = 12


# =============================================================================
# Exceptions
# =============================================================================


class PullError(Exception):
    """Base exception for pull operations."""

    pass


class ValidationError(PullError):
    """Raised when validation fails."""

    pass


class SnapshotError(PullError):
    """Raised when snapshot operation fails."""

    pass


class SyncError(PullError):
    """Raised when rclone sync fails."""

    def __init__(self, message: str, snapshot_name: str | None = None) -> None:
        super().__init__(message)
        self.snapshot_name = snapshot_name


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class PullConfig:
    """Configuration for pull operation.

    Attributes:
        remote: rclone remote path (source).
        dataset: ZFS dataset path (target).
        config_path: Path to rclone configuration file.
        transfers: Number of parallel transfers.
        tpslimit: Transactions per second limit.
        dry_run: If True, perform trial run with no changes.
        keep_pre_snapshot: If True, don't destroy pre-pull snapshot on success.
        no_pre_snapshot: If True, skip creating pre-pull snapshot.
    """

    remote: str
    dataset: str
    config_path: Path
    transfers: int = DEFAULT_TRANSFERS
    tpslimit: int = DEFAULT_TPSLIMIT
    dry_run: bool = False
    keep_pre_snapshot: bool = False
    no_pre_snapshot: bool = False


@dataclass
class PullResult:
    """Result of a pull operation.

    Attributes:
        success: True if pull completed successfully.
        files_transferred: Number of files transferred.
        snapshot_name: Name of pre-pull snapshot (if created and preserved).
    """

    success: bool
    files_transferred: int
    snapshot_name: str = ""


# =============================================================================
# Pure Functions
# =============================================================================


def get_pre_pull_snapshot_name(dataset: str, timestamp: str) -> str:
    """Get the full snapshot name for a pre-pull snapshot.

    Args:
        dataset: ZFS dataset path.
        timestamp: Timestamp string (e.g., "2026-01-03T12-00-00Z").

    Returns:
        Full snapshot name (e.g., "testpool/target@dropboxpull-pre-2026-01-03T12-00-00Z").
    """
    return f"{dataset}@{PRE_PULL_SNAPSHOT_PREFIX}-{timestamp}"


def build_pull_command(
    remote: str,
    mountpoint: Path,
    config_path: Path,
    transfers: int,
    tpslimit: int,
    dry_run: bool,
    rclone_bin: str | None = None,
) -> list[str]:
    """Build rclone sync command for pull operation.

    Args:
        remote: rclone remote path (source).
        mountpoint: Local mountpoint path (destination).
        config_path: Path to rclone configuration file.
        transfers: Number of parallel transfers.
        tpslimit: Transactions per second limit.
        dry_run: If True, add --dry-run flag.
        rclone_bin: Path to rclone binary (uses PATH if None).

    Returns:
        List of command arguments for subprocess.
    """
    if rclone_bin is None:
        rclone_bin = shutil.which("rclone") or "/usr/bin/rclone"

    cmd = [
        rclone_bin,
        "sync",
        remote,
        str(mountpoint),
        "--config",
        str(config_path),
        "--transfers",
        str(transfers),
        "--tpslimit",
        str(tpslimit),
        "--links",  # Restore symlinks from .rclonelink files
        "--exclude",
        ".versions/**",  # Skip version backup directory
    ]

    if dry_run:
        cmd.append("--dry-run")

    return cmd


# =============================================================================
# Protocol for Dependency Injection
# =============================================================================


class PullOperations(Protocol):
    """Protocol for pull operations.

    This protocol defines the interface for pull operations,
    allowing for dependency injection and testing with fakes.
    """

    def validate_dataset(self, dataset: str) -> Path:
        """Validate dataset exists and return mountpoint."""
        ...

    def validate_remote(self, remote: str, config_path: Path) -> None:
        """Validate rclone remote configuration."""
        ...

    def create_pre_pull_snapshot(self, dataset: str, timestamp: str) -> str:
        """Create pre-pull snapshot and return full snapshot name."""
        ...

    def run_rclone_pull(
        self,
        remote: str,
        mountpoint: Path,
        config_path: Path,
        transfers: int,
        tpslimit: int,
        dry_run: bool,
    ) -> int:
        """Run rclone pull and return files transferred."""
        ...

    def destroy_snapshot(self, snapshot_name: str) -> None:
        """Destroy snapshot."""
        ...


# =============================================================================
# Pull Orchestrator
# =============================================================================


class PullOrchestrator:
    """Orchestrates the pull workflow.

    The workflow:
    1. Validate dataset and get mountpoint
    2. Validate rclone remote
    3. Create pre-pull snapshot (unless no_pre_snapshot)
    4. Run rclone sync
    5. Destroy snapshot (on success, unless keep_pre_snapshot)
    """

    def __init__(
        self,
        operations: PullOperations,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize orchestrator.

        Args:
            operations: Implementation of PullOperations.
            logger: Logger for operation diagnostics.
        """
        self._ops = operations
        self._logger = logger or logging.getLogger(__name__)

    def run(self, config: PullConfig) -> PullResult:
        """Execute pull workflow.

        Args:
            config: Pull configuration.

        Returns:
            PullResult with success status and details.

        Raises:
            ValidationError: If validation fails.
            SnapshotError: If snapshot operation fails.
            SyncError: If rclone sync fails.
        """
        # Generate timestamp for snapshot
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        snapshot_name = ""
        files_transferred = 0

        # Step 1: Validate dataset
        self._logger.info(f"Validating dataset: {config.dataset}")
        mountpoint = self._ops.validate_dataset(config.dataset)

        # Step 2: Validate remote
        self._logger.info(f"Validating remote: {config.remote}")
        self._ops.validate_remote(config.remote, config.config_path)

        # Step 3: Create pre-pull snapshot (unless skipped)
        if not config.no_pre_snapshot:
            self._logger.info(f"Creating pre-pull snapshot")
            snapshot_name = self._ops.create_pre_pull_snapshot(config.dataset, timestamp)
            self._logger.info(f"Created snapshot: {snapshot_name}")

        try:
            # Step 4: Run rclone pull
            self._logger.info(f"Pulling from {config.remote} to {mountpoint}")
            files_transferred = self._ops.run_rclone_pull(
                remote=config.remote,
                mountpoint=mountpoint,
                config_path=config.config_path,
                transfers=config.transfers,
                tpslimit=config.tpslimit,
                dry_run=config.dry_run,
            )
            self._logger.info(f"Pull complete: {files_transferred} files transferred")

        except Exception as e:
            # On failure, preserve snapshot for rollback
            if snapshot_name:
                self._logger.warning(f"Pull failed. Pre-pull snapshot preserved: {snapshot_name}")
                self._logger.info(f"To rollback: zfs rollback {snapshot_name}")
                if isinstance(e, SyncError):
                    e.snapshot_name = snapshot_name
                else:
                    raise SyncError(
                        f"Sync failed: {e}. "
                        f"Pre-pull snapshot preserved for rollback: {snapshot_name}",
                        snapshot_name=snapshot_name,
                    ) from e
            raise

        # Step 5: Destroy snapshot (on success, unless keep_pre_snapshot)
        if snapshot_name and not config.keep_pre_snapshot:
            self._logger.info(f"Destroying pre-pull snapshot: {snapshot_name}")
            try:
                self._ops.destroy_snapshot(snapshot_name)
            except Exception as e:
                self._logger.warning(f"Failed to destroy snapshot: {e}")

        return PullResult(
            success=True,
            files_transferred=files_transferred,
            snapshot_name=snapshot_name if config.keep_pre_snapshot else "",
        )


# =============================================================================
# Real Operations Implementation
# =============================================================================


class RealPullOperations:
    """Real implementation of PullOperations using ZFS and rclone.

    This class wraps the actual ZFS and rclone operations.
    """

    def __init__(self, logger: logging.Logger) -> None:
        """Initialize with logger."""
        self._logger = logger

    def validate_dataset(self, dataset: str) -> Path:
        """Validate dataset exists and return mountpoint.

        Args:
            dataset: ZFS dataset path.

        Returns:
            Path to mountpoint.

        Raises:
            ValidationError: If dataset doesn't exist.
        """
        from cloud_mirror.zfs import ZfsError, run_zfs_command

        try:
            result = run_zfs_command(
                ["zfs", "get", "-H", "-o", "value", "mountpoint", dataset],
                self._logger,
            )
            mountpoint = result.stdout.strip()
            if mountpoint == "none" or mountpoint == "-":
                raise ValidationError(f"Dataset '{dataset}' has no mountpoint")
            return Path(mountpoint)
        except ZfsError as e:
            raise ValidationError(f"Dataset '{dataset}' does not exist: {e}") from e

    def validate_remote(self, remote: str, config_path: Path) -> None:
        """Validate rclone remote configuration.

        Args:
            remote: rclone remote path (e.g., "dropbox:path").
            config_path: Path to rclone configuration file.

        Raises:
            ValidationError: If remote is not configured.
        """
        import subprocess

        remote_name = remote.split(":")[0]
        rclone_bin = shutil.which("rclone") or "/usr/bin/rclone"

        try:
            result = subprocess.run(  # noqa: S603, S607
                [rclone_bin, "--config", str(config_path), "listremotes"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise ValidationError(f"Failed to list rclone remotes: {result.stderr}")

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

    def create_pre_pull_snapshot(self, dataset: str, timestamp: str) -> str:
        """Create pre-pull snapshot.

        Args:
            dataset: ZFS dataset path.
            timestamp: Timestamp string.

        Returns:
            Full snapshot name.

        Raises:
            SnapshotError: If snapshot creation fails.
        """
        from cloud_mirror.zfs import ZfsError, run_zfs_command

        snapshot_name = get_pre_pull_snapshot_name(dataset, timestamp)

        try:
            run_zfs_command(
                ["zfs", "snapshot", snapshot_name],
                self._logger,
            )
            return snapshot_name
        except ZfsError as e:
            raise SnapshotError(f"Failed to create pre-pull snapshot: {e}") from e

    def run_rclone_pull(
        self,
        remote: str,
        mountpoint: Path,
        config_path: Path,
        transfers: int,
        tpslimit: int,
        dry_run: bool,
    ) -> int:
        """Run rclone pull operation.

        Args:
            remote: rclone remote path (source).
            mountpoint: Local mountpoint path (destination).
            config_path: Path to rclone configuration file.
            transfers: Number of parallel transfers.
            tpslimit: Transactions per second limit.
            dry_run: If True, perform trial run.

        Returns:
            Number of files transferred.

        Raises:
            SyncError: If sync fails.
        """
        import subprocess

        cmd = build_pull_command(
            remote=remote,
            mountpoint=mountpoint,
            config_path=config_path,
            transfers=transfers,
            tpslimit=tpslimit,
            dry_run=dry_run,
        )

        self._logger.debug(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
            )
            if result.returncode != 0:
                raise SyncError(f"rclone failed with exit code {result.returncode}: {result.stderr}")

            # Count files from rclone output
            # For now, return a placeholder (rclone stats parsing can be added later)
            return 0  # TODO: Parse rclone output for actual count

        except subprocess.TimeoutExpired as e:
            raise SyncError(f"rclone timed out: {e}") from e
        except FileNotFoundError as e:
            raise SyncError(f"rclone not found: {e}") from e

    def destroy_snapshot(self, snapshot_name: str) -> None:
        """Destroy snapshot.

        Args:
            snapshot_name: Full snapshot name to destroy.
        """
        from cloud_mirror.zfs import run_zfs_command

        run_zfs_command(
            ["zfs", "destroy", snapshot_name],
            self._logger,
        )


# =============================================================================
# Main Entry Point
# =============================================================================


def run_pull(
    remote: str,
    dataset: str,
    config_path: Path | None = None,
    transfers: int = DEFAULT_TRANSFERS,
    tpslimit: int = DEFAULT_TPSLIMIT,
    dry_run: bool = False,
    keep_pre_snapshot: bool = False,
    no_pre_snapshot: bool = False,
    verbose: int = 0,
) -> int:
    """Execute a pull operation.

    This is the main entry point for the pull command.

    Args:
        remote: rclone remote path (source).
        dataset: ZFS dataset path (target).
        config_path: Path to rclone config, or None for default.
        transfers: Number of parallel transfers.
        tpslimit: Transactions per second limit.
        dry_run: If True, perform trial run.
        keep_pre_snapshot: If True, keep pre-pull snapshot after success.
        no_pre_snapshot: If True, skip creating pre-pull snapshot.
        verbose: Verbosity level (0=quiet, 1=info, 2=debug).

    Returns:
        Exit code: 0 for success, 1 for failure.
    """
    import sys

    # Setup logging
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
        logger.info(f"Starting pull: {remote} -> {dataset}")

        operations = RealPullOperations(logger)
        orchestrator = PullOrchestrator(operations, logger)

        config = PullConfig(
            remote=remote,
            dataset=dataset,
            config_path=config_path,
            transfers=transfers,
            tpslimit=tpslimit,
            dry_run=dry_run,
            keep_pre_snapshot=keep_pre_snapshot,
            no_pre_snapshot=no_pre_snapshot,
        )

        result = orchestrator.run(config)

        if result.success:
            logger.info(f"Pull complete: {result.files_transferred} files transferred")
            return 0
        else:
            return 1

    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)  # noqa: T201
        print("Suggestion: Check that the dataset and remote exist.", file=sys.stderr)  # noqa: T201
        return 1

    except SnapshotError as e:
        print(f"Error: {e}", file=sys.stderr)  # noqa: T201
        print("Suggestion: Check ZFS permissions and disk space.", file=sys.stderr)  # noqa: T201
        return 1

    except SyncError as e:
        print(f"Error: {e}", file=sys.stderr)  # noqa: T201
        if e.snapshot_name:
            print(f"Pre-pull snapshot preserved: {e.snapshot_name}", file=sys.stderr)  # noqa: T201
            print(f"To rollback: zfs rollback {e.snapshot_name}", file=sys.stderr)  # noqa: T201
        print("Suggestion: Check network connectivity and rclone configuration.", file=sys.stderr)  # noqa: T201
        return 1

    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)  # noqa: T201
        return 130

    except Exception as e:
        logger.exception("Unexpected error")
        print(f"Error: Unexpected error: {e}", file=sys.stderr)  # noqa: T201
        return 1
