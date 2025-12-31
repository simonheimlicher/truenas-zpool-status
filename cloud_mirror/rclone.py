"""
rclone operations for cloud-mirror.

This module provides pure functions for building rclone commands,
parsing rclone output, and filtering output by verbosity level.

Level 1 (Unit): All functions in this module are pure - no I/O, no subprocess.
"""

from __future__ import annotations

from dataclasses import dataclass
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
