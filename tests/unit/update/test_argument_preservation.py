"""Tests for argument preservation during re-execution (FR2 of story-76)."""

from __future__ import annotations

import sys
from unittest.mock import patch

from cloud_mirror.update import reexec_with_new_code


def test_preserves_positional_arguments() -> None:
    """Test that positional arguments are preserved.

    GIVEN command with positional args: cloud_mirror push source dest
    WHEN reexec_with_new_code() is called
    THEN new command preserves argument order
    """
    test_argv = ["cloud_mirror", "push", "source", "dest"]
    with patch("sys.argv", test_argv):
        with patch("cloud_mirror.update.os.execv") as mock_execv:
            reexec_with_new_code()

            cmd = mock_execv.call_args[0][1]
            # Verify args after "-m cloud_mirror" match original
            assert cmd[3:] == ["push", "source", "dest"]


def test_preserves_flags_with_values() -> None:
    """Test that flags with values are preserved.

    GIVEN command with flags: cloud_mirror --config /path push source dest
    WHEN reexec_with_new_code() is called
    THEN flags and their values are preserved
    """
    test_argv = [
        "cloud_mirror",
        "--config",
        "/path/to/config",
        "push",
        "source",
        "dest",
    ]
    with patch("sys.argv", test_argv):
        with patch("cloud_mirror.update.os.execv") as mock_execv:
            reexec_with_new_code()

            cmd = mock_execv.call_args[0][1]
            # Verify full argument list preserved
            assert cmd[3:] == ["--config", "/path/to/config", "push", "source", "dest"]


def test_preserves_boolean_flags() -> None:
    """Test that boolean flags are preserved.

    GIVEN command with boolean flags: cloud_mirror --verbose --dry-run push
    WHEN reexec_with_new_code() is called
    THEN boolean flags are preserved
    """
    test_argv = ["cloud_mirror", "--verbose", "--dry-run", "push", "source", "dest"]
    with patch("sys.argv", test_argv):
        with patch("cloud_mirror.update.os.execv") as mock_execv:
            reexec_with_new_code()

            cmd = mock_execv.call_args[0][1]
            assert cmd[3:] == ["--verbose", "--dry-run", "push", "source", "dest"]


def test_preserves_args_with_special_characters() -> None:
    """Test arguments with special characters are preserved.

    GIVEN arguments contain spaces, quotes, special chars
    WHEN reexec_with_new_code() is called
    THEN special characters are preserved correctly
    """
    test_argv = [
        "cloud_mirror",
        "push",
        "tank/my data",
        "dropbox:backup/my folder",
        "--filter",
        "*.txt",
    ]
    with patch("sys.argv", test_argv):
        with patch("cloud_mirror.update.os.execv") as mock_execv:
            reexec_with_new_code()

            cmd = mock_execv.call_args[0][1]
            # Verify all arguments preserved exactly
            assert cmd[3:] == [
                "push",
                "tank/my data",
                "dropbox:backup/my folder",
                "--filter",
                "*.txt",
            ]


def test_empty_args_handled() -> None:
    """Test that empty sys.argv[1:] is handled correctly.

    GIVEN sys.argv is just ["cloud_mirror"] (no args)
    WHEN reexec_with_new_code() is called
    THEN command is [sys.executable, "-m", "cloud_mirror"] with no extra args
    """
    test_argv = ["cloud_mirror"]
    with patch("sys.argv", test_argv):
        with patch("cloud_mirror.update.os.execv") as mock_execv:
            reexec_with_new_code()

            cmd = mock_execv.call_args[0][1]
            # Should only have the base command
            assert cmd == [sys.executable, "-m", "cloud_mirror"]
