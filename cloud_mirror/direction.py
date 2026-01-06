"""
Direction detection for cloud-mirror.

This module detects sync direction (PUSH or PULL) based on argument order.
rclone remotes (containing colon) are distinguished from ZFS datasets.

Detection Rules:
- If first arg contains ":" before "/" -> it's a remote -> PULL
- If second arg contains ":" before "/" -> it's a remote -> PUSH
- If both or neither have colons in the right position -> error
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class SyncDirection(Enum):
    """Sync direction: PUSH (local to remote) or PULL (remote to local)."""

    PUSH = auto()
    PULL = auto()


@dataclass(frozen=True)
class SyncEndpoints:
    """Parsed sync endpoints with detected direction.

    Attributes:
        direction: PUSH (dataset -> remote) or PULL (remote -> dataset)
        zfs_dataset: The ZFS dataset path (source for push, target for pull)
        remote: The rclone remote path (target for push, source for pull)
    """

    direction: SyncDirection
    zfs_dataset: str
    remote: str


class DirectionError(Exception):
    """Error raised when sync direction cannot be determined."""

    pass


def is_rclone_remote(arg: str) -> bool:
    """Determine if an argument is an rclone remote.

    An rclone remote has the format "remotename:path" where:
    - remotename is alphanumeric with underscores/hyphens
    - The colon appears BEFORE any slash

    ZFS datasets like "tank/vm:disk0" have a slash before the colon,
    so they are not detected as remotes.

    Args:
        arg: Argument string to check.

    Returns:
        True if the argument appears to be an rclone remote.
    """
    if ":" not in arg:
        return False

    colon_pos = arg.index(":")
    slash_pos = arg.find("/")

    # If there's a slash and it comes before the colon, it's a ZFS dataset
    if slash_pos != -1 and slash_pos < colon_pos:
        return False

    # Has colon with no slash before it -> remote
    return True


def detect_direction(arg1: str, arg2: str) -> SyncEndpoints:
    """Detect sync direction from argument order.

    The direction is determined by which argument is an rclone remote:
    - arg1 is remote, arg2 is dataset -> PULL (remote to local)
    - arg1 is dataset, arg2 is remote -> PUSH (local to remote)

    Args:
        arg1: First positional argument.
        arg2: Second positional argument.

    Returns:
        SyncEndpoints with direction, zfs_dataset, and remote.

    Raises:
        DirectionError: If both arguments are remotes, or neither is.
    """
    arg1_is_remote = is_rclone_remote(arg1)
    arg2_is_remote = is_rclone_remote(arg2)

    if arg1_is_remote and arg2_is_remote:
        raise DirectionError(
            f"Both arguments appear to be rclone remotes: '{arg1}' and '{arg2}'. "
            "One must be a ZFS dataset (no colon, or colon after slash)."
        )

    if not arg1_is_remote and not arg2_is_remote:
        raise DirectionError(
            f"Neither argument appears to be an rclone remote: '{arg1}' and '{arg2}'. "
            "One must be a remote (format: 'remotename:path')."
        )

    if arg1_is_remote:
        # Remote first -> PULL (remote to local)
        return SyncEndpoints(
            direction=SyncDirection.PULL,
            zfs_dataset=arg2,
            remote=arg1,
        )
    else:
        # Dataset first -> PUSH (local to remote)
        return SyncEndpoints(
            direction=SyncDirection.PUSH,
            zfs_dataset=arg1,
            remote=arg2,
        )
