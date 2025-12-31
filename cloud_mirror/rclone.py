"""
rclone operations for cloud-mirror.

This module provides:
- Pure functions for building rclone commands (Level 1 - Unit testable)
- Sync execution function with subprocess (Level 2/3 - Integration testable)

Level 1 (Unit): Pure functions - no I/O, no subprocess
Level 2 (VM): Real rclone with local backend
Level 3 (Internet): Real Dropbox
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# rclone binary path (configurable for testing)
RCLONE_BIN = "/usr/bin/rclone"

# Default sync parameters
DEFAULT_TRANSFERS = 64
DEFAULT_CHECKERS = 8
DEFAULT_TPSLIMIT = 12

# Version backup directory name
VERSIONS_DIR = ".versions"

# Error categories for parsed errors
ErrorCategory = Literal[
    "rate_limit",
    "auth_error",
    "transfer_error",
    "network_error",
    "not_found",
    "permission_denied",
    "unknown",
]


@dataclass(frozen=True)
class RcloneError:
    """Structured representation of an rclone error.

    Attributes:
        category: Error category for handling decisions.
        message: Human-readable error message.
        file: File path if error is file-specific, None otherwise.
        raw: Original raw error line from rclone.
    """

    category: ErrorCategory
    message: str
    file: str | None = None
    raw: str = ""


@dataclass(frozen=True)
class RcloneSyncConfig:
    """Configuration for rclone sync command.

    Attributes:
        source: Source path to sync from.
        destination: rclone destination (e.g., "dropbox:backup").
        config_path: Path to rclone configuration file.
        transfers: Number of parallel file transfers.
        checkers: Number of parallel checkers.
        tpslimit: Transactions per second limit (for rate limiting).
        dry_run: If True, perform a trial run with no changes.
        keep_versions: Number of versions to keep (0 = no versioning).
        timestamp: Timestamp string for version backup directory.
    """

    source: Path
    destination: str
    config_path: Path
    transfers: int = DEFAULT_TRANSFERS
    checkers: int = DEFAULT_CHECKERS
    tpslimit: int = DEFAULT_TPSLIMIT
    dry_run: bool = False
    keep_versions: int = 0
    timestamp: str = ""


def build_rclone_command(
    config: RcloneSyncConfig,
    rclone_bin: str = RCLONE_BIN,
) -> list[str]:
    """Build rclone sync command from configuration.

    Args:
        config: Sync configuration.
        rclone_bin: Path to rclone binary (injectable for testing).

    Returns:
        Command as list of strings ready for subprocess.
    """
    cmd = [
        rclone_bin,
        "--config", str(config.config_path),
        "sync",
        str(config.source) + "/",  # Trailing slash to sync contents
        config.destination,
        "--transfers", str(config.transfers),
        "--checkers", str(config.checkers),
        "--contimeout", "60s",
        "--timeout", "300s",
        "--retries", "3",
        "--low-level-retries", "10",
        "--links",  # Preserve symlinks as .rclonelink files
        "--checksum",  # Use checksums for comparison (FR1 requirement)
        "--tpslimit", str(config.tpslimit),
        "--order-by", "size,mixed,75",
        "--max-backlog", "10000",
    ]

    # Add backup-dir for versioning if enabled
    if config.keep_versions > 0 and config.timestamp:
        backup_dir = f"{config.destination}/{VERSIONS_DIR}/{config.timestamp}"
        cmd.extend(["--backup-dir", backup_dir])

    if config.dry_run:
        cmd.append("--dry-run")

    # Always use rclone verbose to get progress info, we filter on our side
    cmd.append("--verbose")

    return cmd


def get_version_backup_path(destination: str, timestamp: str) -> str:
    """Get the backup directory path for versioning.

    Args:
        destination: rclone destination (e.g., "dropbox:backup").
        timestamp: Timestamp string for version directory.

    Returns:
        Full path to backup directory.
    """
    return f"{destination}/{VERSIONS_DIR}/{timestamp}"


def parse_rclone_error(line: str) -> RcloneError | None:
    """Parse an rclone error line into structured error.

    Args:
        line: Single line of rclone output.

    Returns:
        RcloneError if line contains an error, None otherwise.
    """
    line = line.strip()

    # Check for ERROR lines
    if "ERROR" not in line and "NOTICE" not in line:
        return None

    # Rate limit errors from Dropbox
    if "too_many_write_operations" in line.lower():
        return RcloneError(
            category="rate_limit",
            message="Dropbox rate limit exceeded. Consider reducing --tpslimit.",
            raw=line,
        )

    if "too_many_requests" in line.lower() or "rate limit" in line.lower():
        return RcloneError(
            category="rate_limit",
            message="Rate limit exceeded. Retry after backoff.",
            raw=line,
        )

    # Authentication errors
    if "token" in line.lower() and ("expired" in line.lower() or "invalid" in line.lower()):
        return RcloneError(
            category="auth_error",
            message="Authentication failed. Run 'rclone config reconnect' to refresh token.",
            raw=line,
        )

    if "unauthorized" in line.lower() or "401" in line:
        return RcloneError(
            category="auth_error",
            message="Authentication failed. Check credentials.",
            raw=line,
        )

    # Network errors
    if "connection" in line.lower() and ("refused" in line.lower() or "reset" in line.lower()):
        return RcloneError(
            category="network_error",
            message="Network connection failed. Check internet connectivity.",
            raw=line,
        )

    if "timeout" in line.lower() or "timed out" in line.lower():
        return RcloneError(
            category="network_error",
            message="Operation timed out. Network may be slow or unstable.",
            raw=line,
        )

    # Not found errors
    if "not found" in line.lower() or "doesn't exist" in line.lower():
        return RcloneError(
            category="not_found",
            message="Resource not found.",
            raw=line,
        )

    # Permission errors
    if "permission denied" in line.lower() or "access denied" in line.lower():
        return RcloneError(
            category="permission_denied",
            message="Permission denied. Check file/folder permissions.",
            raw=line,
        )

    # File-specific transfer errors (e.g., "ERROR : file.txt: Failed to copy")
    if "ERROR" in line and ": " in line:
        parts = line.split(": ", 2)
        if len(parts) >= 3:
            # Format: "ERROR : path/to/file: message"
            file_path = parts[1].strip()
            error_msg = parts[2].strip() if len(parts) > 2 else "Unknown error"
            return RcloneError(
                category="transfer_error",
                message=error_msg,
                file=file_path,
                raw=line,
            )

    # Generic error
    if "ERROR" in line:
        return RcloneError(
            category="unknown",
            message=line,
            raw=line,
        )

    # NOTICE lines that aren't errors (skip modification time notice)
    if "NOTICE" in line:
        if "Forced to upload files to set modification times" in line:
            return None  # Not an error, just informational
        # Other notices might be warnings worth capturing
        return RcloneError(
            category="unknown",
            message=line,
            raw=line,
        )

    return None


def filter_rclone_output(
    lines: list[str],
    verbosity: int,
) -> list[str]:
    """Filter rclone output lines based on verbosity level.

    Args:
        lines: List of rclone output lines.
        verbosity: Verbosity level (0=errors only, 1=progress, 2=all).

    Returns:
        Filtered list of lines to display.
    """
    result = []
    for line in lines:
        if should_show_line(line, verbosity):
            result.append(line)
    return result


def should_show_line(line: str, verbosity: int) -> bool:
    """Determine if a line should be shown based on verbosity level.

    Args:
        line: Single line of rclone output.
        verbosity: Verbosity level.
            0: Only errors and rate limit notices (for cron email alerts)
            1: Progress summaries but not individual file transfers
            2+: Everything including individual file transfers

    Returns:
        True if line should be shown, False otherwise.
    """
    # Always show NOTICE (rate limits, errors) - important for cron alerts
    # But filter out the unhelpful Dropbox modification time notice
    if "NOTICE:" in line:
        if "Forced to upload files to set modification times" in line:
            return False
        return True

    # Always show ERROR
    if "ERROR:" in line:
        return True

    if verbosity == 0:
        return False

    if verbosity == 1:
        # Show progress lines but not individual file transfers
        # Individual file lines look like: "INFO  : path/to/file: Copied (new)"
        # Progress lines look like: "INFO  : \nTransferred:" or "INFO  : Starting transaction"
        if "INFO  :" in line:
            # Check if it's a file transfer line (contains ": Copied" or ": Moved" etc.)
            if ": Copied (" in line or ": Moved (" in line or ": Deleted" in line:
                return False
            # Skip "src and dst identical" lines too
            if "src and dst identical" in line:
                return False
        return True

    # Level 2+: show everything
    return True


# =============================================================================
# Sync Result and Errors (Level 2/3 - Integration)
# =============================================================================


@dataclass(frozen=True)
class SyncResult:
    """Result of an rclone sync operation.

    Attributes:
        success: True if sync completed without errors.
        files_transferred: Number of files transferred.
        bytes_transferred: Total bytes transferred.
        errors: List of parsed errors encountered during sync.
        stdout: Raw stdout from rclone.
        stderr: Raw stderr from rclone.
        returncode: Exit code from rclone process.
    """

    success: bool
    files_transferred: int = 0
    bytes_transferred: int = 0
    errors: list[RcloneError] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


class RcloneSyncError(Exception):
    """Raised when rclone sync fails.

    Provides structured error information and actionable fix suggestions.

    Attributes:
        message: Human-readable error message.
        errors: List of parsed RcloneError objects.
        suggestion: Actionable fix suggestion.
        returncode: Exit code from rclone process.
    """

    def __init__(
        self,
        message: str,
        errors: list[RcloneError] | None = None,
        suggestion: str = "",
        returncode: int = 1,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.errors = errors or []
        self.suggestion = suggestion
        self.returncode = returncode

    def __str__(self) -> str:
        result = self.message
        if self.suggestion:
            result += f"\n\nSuggestion: {self.suggestion}"
        return result


# Default timeout for rclone operations (10 minutes)
SYNC_TIMEOUT_SECONDS = 600

# Logger for sync operations
_logger = logging.getLogger(__name__)


def run_rclone_sync(
    config: RcloneSyncConfig,
    rclone_bin: str = RCLONE_BIN,
    timeout: int = SYNC_TIMEOUT_SECONDS,
    logger: logging.Logger | None = None,
) -> SyncResult:
    """Execute rclone sync operation.

    Syncs files from source to destination using rclone. Symlinks are
    converted to .rclonelink files. Directory structure is preserved.

    Args:
        config: Sync configuration with source, destination, and options.
        rclone_bin: Path to rclone binary (injectable for testing).
        timeout: Timeout in seconds for the sync operation.
        logger: Logger for diagnostics (uses module logger if not provided).

    Returns:
        SyncResult with success status and transfer statistics.

    Raises:
        RcloneSyncError: If sync fails with helpful error message and suggestion.

    Examples:
        >>> config = RcloneSyncConfig(
        ...     source=Path("/data"),
        ...     destination="dropbox:backup",
        ...     config_path=Path("~/.config/rclone/rclone.conf"),
        ... )
        >>> result = run_rclone_sync(config)
        >>> if result.success:
        ...     print(f"Synced {result.files_transferred} files")
    """
    log = logger or _logger

    # Build the command
    cmd = build_rclone_command(config, rclone_bin)
    log.debug(f"Running rclone: {' '.join(cmd)}")

    # Execute rclone
    try:
        result = subprocess.run(  # noqa: S603 - cmd is built from RcloneSyncConfig, not user input
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise RcloneSyncError(
            message=f"Sync timed out after {timeout} seconds",
            suggestion="Consider increasing timeout or syncing fewer files.",
            returncode=-1,
        ) from e
    except FileNotFoundError as e:
        raise RcloneSyncError(
            message=f"rclone binary not found: {rclone_bin}",
            suggestion="Install rclone or provide correct path via rclone_bin parameter.",
            returncode=-1,
        ) from e

    # Parse output for errors
    all_lines = result.stdout.splitlines() + result.stderr.splitlines()
    errors = []
    for line in all_lines:
        parsed = parse_rclone_error(line)
        if parsed:
            errors.append(parsed)

    # Parse transfer statistics from output
    files_transferred, bytes_transferred = _parse_transfer_stats(result.stdout)

    # Check for failure
    if result.returncode != 0:
        # Determine the primary error category
        primary_error = errors[0] if errors else None
        suggestion = _get_error_suggestion(primary_error)

        raise RcloneSyncError(
            message=f"Sync failed with exit code {result.returncode}",
            errors=errors,
            suggestion=suggestion,
            returncode=result.returncode,
        )

    return SyncResult(
        success=True,
        files_transferred=files_transferred,
        bytes_transferred=bytes_transferred,
        errors=errors,  # May have warnings even on success
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
    )


def _parse_transfer_stats(stdout: str) -> tuple[int, int]:
    """Parse transfer statistics from rclone output.

    Args:
        stdout: rclone stdout output.

    Returns:
        Tuple of (files_transferred, bytes_transferred).
    """
    files = 0
    bytes_total = 0

    for line in stdout.splitlines():
        # Look for lines like "Transferred:   10 / 10, 100%"
        if "Transferred:" in line and "/" in line:
            try:
                # Extract the count before the slash
                parts = line.split("Transferred:")[-1].strip().split("/")
                if parts:
                    files = int(parts[0].strip().split()[0])
            except (ValueError, IndexError):
                pass

        # Look for byte count lines like "Transferred:    1.234 MiB"
        if "Transferred:" in line and ("KiB" in line or "MiB" in line or "GiB" in line):
            try:
                # Parse size with unit
                size_part = line.split("Transferred:")[-1].strip().split(",")[0]
                bytes_total = _parse_size_to_bytes(size_part)
            except (ValueError, IndexError):
                pass

    return files, bytes_total


def _parse_size_to_bytes(size_str: str) -> int:
    """Parse size string like '1.5 MiB' to bytes.

    Args:
        size_str: Size string with unit (e.g., "1.5 MiB", "100 KiB").

    Returns:
        Size in bytes.
    """
    size_str = size_str.strip()
    units = {
        "B": 1,
        "KiB": 1024,
        "MiB": 1024 * 1024,
        "GiB": 1024 * 1024 * 1024,
        "TiB": 1024 * 1024 * 1024 * 1024,
        # Also support KB/MB/GB (decimal)
        "KB": 1000,
        "MB": 1000 * 1000,
        "GB": 1000 * 1000 * 1000,
    }

    for unit, multiplier in units.items():
        if unit in size_str:
            try:
                value = float(size_str.replace(unit, "").strip())
                return int(value * multiplier)
            except ValueError:
                pass

    # Try parsing as plain bytes
    try:
        return int(float(size_str))
    except ValueError:
        return 0


def _get_error_suggestion(error: RcloneError | None) -> str:
    """Get actionable suggestion for an rclone error.

    Args:
        error: Parsed rclone error, or None.

    Returns:
        Human-readable suggestion for fixing the error.
    """
    if error is None:
        return "Check rclone logs for details."

    suggestions = {
        "rate_limit": "Reduce --tpslimit or wait before retrying.",
        "auth_error": "Run 'rclone config reconnect <remote>' to refresh token.",
        "network_error": "Check internet connectivity and retry.",
        "not_found": "Verify the remote path exists.",
        "permission_denied": "Check file/folder permissions on source and destination.",
        "transfer_error": f"Check the file: {error.file}" if error.file else "Check transfer logs.",
        "unknown": "Check rclone logs for details.",
    }

    return suggestions.get(error.category, "Check rclone logs for details.")
