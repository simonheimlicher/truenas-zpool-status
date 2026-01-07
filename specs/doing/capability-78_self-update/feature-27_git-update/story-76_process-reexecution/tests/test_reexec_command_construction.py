"""Tests for reexec_with_new_code command construction (FR1 of story-76)."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import patch

from cloud_mirror.update import reexec_with_new_code

if TYPE_CHECKING:
    from unittest.mock import MagicMock


def test_constructs_correct_command_with_no_args() -> None:
    """Test command construction when no arguments provided.

    GIVEN sys.argv is ["cloud_mirror"]
    WHEN reexec_with_new_code() is called
    THEN it constructs [sys.executable, "-m", "cloud_mirror"]
    """
    with patch("sys.argv", ["cloud_mirror"]):
        with patch("cloud_mirror.update.os.execv") as mock_execv:
            reexec_with_new_code()

            # Verify os.execv was called
            assert mock_execv.called
            call_args = mock_execv.call_args

            # First arg is executable
            assert call_args[0][0] == sys.executable

            # Second arg is command list
            expected_cmd = [sys.executable, "-m", "cloud_mirror"]
            assert call_args[0][1] == expected_cmd


def test_constructs_correct_command_with_args() -> None:
    """Test command construction preserves arguments.

    GIVEN sys.argv is ["cloud_mirror", "push", "tank/data", "dropbox:backup"]
    WHEN reexec_with_new_code() is called
    THEN it constructs [sys.executable, "-m", "cloud_mirror", "push", "tank/data", "dropbox:backup"]
    """
    test_argv = ["cloud_mirror", "push", "tank/data", "dropbox:backup"]
    with patch("sys.argv", test_argv):
        with patch("cloud_mirror.update.os.execv") as mock_execv:
            reexec_with_new_code()

            assert mock_execv.called
            call_args = mock_execv.call_args

            # Verify command includes all original arguments
            expected_cmd = [
                sys.executable,
                "-m",
                "cloud_mirror",
                "push",
                "tank/data",
                "dropbox:backup",
            ]
            assert call_args[0][1] == expected_cmd


def test_constructs_correct_command_with_flags() -> None:
    """Test command construction with flags and options.

    GIVEN sys.argv includes flags like --config /path/to/config
    WHEN reexec_with_new_code() is called
    THEN all flags are preserved in command
    """
    test_argv = [
        "cloud_mirror",
        "push",
        "tank/data",
        "dropbox:backup",
        "--config",
        "/path/to/config",
        "--verbose",
    ]
    with patch("sys.argv", test_argv):
        with patch("cloud_mirror.update.os.execv") as mock_execv:
            reexec_with_new_code()

            assert mock_execv.called
            call_args = mock_execv.call_args

            # Verify all flags preserved
            expected_cmd = [
                sys.executable,
                "-m",
                "cloud_mirror",
                "push",
                "tank/data",
                "dropbox:backup",
                "--config",
                "/path/to/config",
                "--verbose",
            ]
            assert call_args[0][1] == expected_cmd


def test_uses_sys_executable() -> None:
    """Test that sys.executable is used for re-execution.

    GIVEN sys.executable points to current Python interpreter
    WHEN reexec_with_new_code() is called
    THEN os.execv is called with sys.executable as first argument
    """
    with patch("sys.argv", ["cloud_mirror"]):
        with patch("cloud_mirror.update.os.execv") as mock_execv:
            reexec_with_new_code()

            # First argument to execv should be sys.executable
            assert mock_execv.call_args[0][0] == sys.executable
