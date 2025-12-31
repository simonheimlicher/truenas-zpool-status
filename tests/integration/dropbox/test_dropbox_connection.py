"""
Smoke tests for Dropbox connectivity (Level 3).

These tests verify that the Dropbox test account is properly configured
and accessible. If these fail, no other Level 3 tests can pass.

Run with: uv run --extra dev pytest tests/integration/dropbox/ -v
"""

import subprocess
from pathlib import Path

import pytest


@pytest.mark.internet_required
class TestDropboxConnection:
    """Verify Dropbox test account is accessible."""

    def test_token_is_available(self, dropbox_token: str) -> None:
        """GIVEN .env file WHEN loading THEN DROPBOX_TEST_TOKEN is set."""
        assert dropbox_token is not None
        assert len(dropbox_token) > 100  # Tokens are long JSON strings

    def test_can_list_remote(self, dropbox_config: Path) -> None:
        """GIVEN valid token WHEN listing remote THEN succeeds."""
        result = subprocess.run(
            ["rclone", "lsd", "dropbox-test:", "--config", str(dropbox_config)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Failed to list Dropbox: {result.stderr}"

    def test_can_create_and_delete_folder(self, dropbox_config: Path) -> None:
        """GIVEN valid token WHEN creating folder THEN folder exists and can be deleted."""
        import uuid

        folder_name = f"smoke-test-{uuid.uuid4().hex[:8]}"
        remote_path = f"dropbox-test:cloud-mirror-test/{folder_name}"

        # Create folder
        result = subprocess.run(
            ["rclone", "mkdir", remote_path, "--config", str(dropbox_config)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Failed to create folder: {result.stderr}"

        try:
            # Verify folder exists
            result = subprocess.run(
                ["rclone", "lsd", "dropbox-test:cloud-mirror-test", "--config", str(dropbox_config)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert folder_name in result.stdout, f"Folder not found in listing: {result.stdout}"
        finally:
            # Cleanup
            subprocess.run(
                ["rclone", "rmdir", remote_path, "--config", str(dropbox_config)],
                capture_output=True,
                timeout=30,
            )

    def test_fixture_creates_isolated_folder(
        self, dropbox_test_folder: str, dropbox_config: Path
    ) -> None:
        """GIVEN dropbox_test_folder fixture WHEN used THEN creates isolated folder."""
        # The fixture already created the folder, just verify it exists
        result = subprocess.run(
            ["rclone", "lsd", dropbox_test_folder, "--config", str(dropbox_config)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Empty folder returns 0 but empty output
        assert result.returncode == 0, f"Folder not accessible: {result.stderr}"
