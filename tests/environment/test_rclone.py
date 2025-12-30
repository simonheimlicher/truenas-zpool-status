"""
Tests for rclone test infrastructure (graduated from Feature-76).

This is a smoke test - if it fails, Capability-27 tests cannot run.
The error message points directly at Feature-76 for diagnosis.
"""

import subprocess
from pathlib import Path


def test_rclone_mock_remote_available() -> None:
    """Verify rclone test infrastructure is ready for Capability-27."""
    config_path = Path(__file__).parent.parent / "rclone-test.conf"

    result = subprocess.run(
        ["rclone", "--config", str(config_path), "listremotes"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0 and "testremote:" in result.stdout, (
        f"rclone mock remote not available. "
        f"Check: (1) rclone installed, (2) tests/rclone-test.conf exists. "
        f"See Feature-76 (mock-rclone-remote). Error: {result.stderr}"
    )
