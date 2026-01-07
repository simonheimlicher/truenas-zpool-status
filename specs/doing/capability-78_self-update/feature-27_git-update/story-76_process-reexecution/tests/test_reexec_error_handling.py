"""Tests for error handling in re-execution (FR3 of story-76)."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from cloud_mirror.update import reexec_with_new_code


def test_handles_os_error_gracefully() -> None:
    """Test that OSError is caught and handled.

    GIVEN os.execv raises OSError
    WHEN reexec_with_new_code() is called
    THEN exception is caught and function returns normally
    AND no exception propagates to caller
    """
    with patch("sys.argv", ["cloud_mirror"]):
        with patch("cloud_mirror.update.os.execv") as mock_execv:
            # Simulate execv failure
            mock_execv.side_effect = OSError("Permission denied")

            # Should not raise exception
            reexec_with_new_code()  # Returns normally


def test_logs_error_on_failure() -> None:
    """Test that failures are logged appropriately.

    GIVEN os.execv raises OSError
    WHEN reexec_with_new_code() is called
    THEN ERROR level log is emitted
    AND error message includes exception details
    """
    with patch("sys.argv", ["cloud_mirror"]):
        with patch("cloud_mirror.update.os.execv") as mock_execv:
            mock_execv.side_effect = OSError("Permission denied")

            # Capture log output
            with patch("cloud_mirror.update.logger") as mock_logger:
                reexec_with_new_code()

                # Verify error was logged
                assert mock_logger.error.called
                error_msg = mock_logger.error.call_args[0][0]
                assert (
                    "failed to re-execute" in error_msg.lower()
                    or "permission denied" in error_msg.lower()
                )


def test_logs_info_before_execv() -> None:
    """Test that re-execution attempt is logged at INFO level.

    GIVEN reexec_with_new_code() is called
    WHEN before os.execv is invoked
    THEN INFO level log is emitted with command details
    """
    with patch("sys.argv", ["cloud_mirror", "push", "source", "dest"]):
        with patch("cloud_mirror.update.os.execv") as mock_execv:
            with patch("cloud_mirror.update.logger") as mock_logger:
                reexec_with_new_code()

                # Verify info log was emitted before execv
                assert mock_logger.info.called
                info_msg = mock_logger.info.call_args[0][0]
                assert (
                    "re-executing" in info_msg.lower()
                    or "updated code" in info_msg.lower()
                )


def test_returns_on_failure_allows_caller_to_continue() -> None:
    """Test that caller can handle failure case.

    GIVEN os.execv fails
    WHEN reexec_with_new_code() is called
    THEN function returns normally (doesn't crash)
    AND caller can continue execution with old code
    """
    with patch("sys.argv", ["cloud_mirror"]):
        with patch("cloud_mirror.update.os.execv") as mock_execv:
            mock_execv.side_effect = OSError("Mock failure")

            # Should be able to call and continue
            reexec_with_new_code()
            # This line executes, proving function returned
            assert True


def test_handles_file_not_found_error() -> None:
    """Test handling when Python executable not found.

    GIVEN sys.executable path is invalid
    WHEN os.execv raises FileNotFoundError
    THEN error is caught and logged
    """
    with patch("sys.argv", ["cloud_mirror"]):
        with patch("cloud_mirror.update.os.execv") as mock_execv:
            mock_execv.side_effect = FileNotFoundError("Python not found")

            with patch("cloud_mirror.update.logger") as mock_logger:
                reexec_with_new_code()

                # Should log error for FileNotFoundError too
                assert mock_logger.error.called


def test_different_os_errors_handled() -> None:
    """Test various OSError subtypes are handled.

    GIVEN different OSError types can occur
    WHEN reexec_with_new_code() encounters them
    THEN all are caught and handled gracefully
    """
    error_types = [
        OSError("Permission denied"),
        PermissionError("Cannot execute"),
        FileNotFoundError("Executable not found"),
    ]

    for error in error_types:
        with patch("sys.argv", ["cloud_mirror"]):
            with patch("cloud_mirror.update.os.execv") as mock_execv:
                mock_execv.side_effect = error

                # Should handle each error type
                reexec_with_new_code()  # Returns normally
