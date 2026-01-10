"""Unit tests for config file search functionality.

Tests verify that find_config_file() correctly searches for cloud-mirror.toml
in the expected locations with the correct precedence order.
"""

import pytest
from pathlib import Path
from cloud_mirror.config import find_config_file


class TestTypicalInputs:
    """Tests with typical, expected inputs."""

    def test_find_config_in_parent_directory(self, tmp_path: Path):
        """
        GIVEN cloud-mirror.toml in parent directory
        WHEN find_config_file() is called with package directory
        THEN returns Path to config file in parent
        """
        # Given
        package_dir = tmp_path / "cloud_mirror"
        package_dir.mkdir()
        config_file = tmp_path / "cloud-mirror.toml"
        config_file.write_text("[defaults]\ntransfers = 64\n")

        # When
        result = find_config_file(package_dir)

        # Then
        assert result == config_file
        assert result.exists()

    def test_find_config_in_package_directory(self, tmp_path: Path):
        """
        GIVEN cloud-mirror.toml in package directory itself
        WHEN find_config_file() is called
        THEN returns Path to config file in package directory
        """
        # Given
        package_dir = tmp_path / "cloud_mirror"
        package_dir.mkdir()
        config_file = package_dir / "cloud-mirror.toml"
        config_file.write_text("[defaults]\ntransfers = 64\n")

        # When
        result = find_config_file(package_dir)

        # Then
        assert result == config_file
        assert result.exists()

    def test_search_order_prefers_package_dir_over_parent(self, tmp_path: Path):
        """
        GIVEN cloud-mirror.toml exists in BOTH package directory AND parent
        WHEN find_config_file() is called
        THEN returns config from package directory (higher precedence)
        """
        # Given
        package_dir = tmp_path / "cloud_mirror"
        package_dir.mkdir()

        # Config in both locations (different content to verify which is returned)
        parent_config = tmp_path / "cloud-mirror.toml"
        parent_config.write_text("[defaults]\ntransfers = 32\n")

        package_config = package_dir / "cloud-mirror.toml"
        package_config.write_text("[defaults]\ntransfers = 64\n")

        # When
        result = find_config_file(package_dir)

        # Then
        assert result == package_config
        assert "transfers = 64" in result.read_text()


class TestEdgeCases:
    """Tests with edge cases and error conditions."""

    def test_returns_none_when_config_not_found(self, tmp_path: Path):
        """
        GIVEN no cloud-mirror.toml in any search location
        WHEN find_config_file() is called
        THEN returns None (graceful fallback)
        """
        # Given
        package_dir = tmp_path / "cloud_mirror"
        package_dir.mkdir()
        # No config file created

        # When
        result = find_config_file(package_dir)

        # Then
        assert result is None

    def test_handles_nonexistent_package_directory(self, tmp_path: Path):
        """
        GIVEN package directory does not exist
        WHEN find_config_file() is called
        THEN returns None without raising exception
        """
        # Given
        nonexistent_dir = tmp_path / "nonexistent"
        # Directory NOT created

        # When
        result = find_config_file(nonexistent_dir)

        # Then
        assert result is None
