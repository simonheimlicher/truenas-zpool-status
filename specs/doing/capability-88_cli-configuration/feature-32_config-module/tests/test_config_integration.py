"""Feature integration tests for config module.

Tests verify that parse_toml(), find_config_file(), and load_config()
work together with real filesystem operations (Level 2).
"""

import pytest
from pathlib import Path
from cloud_mirror.config import load_config, ConfigError


def test_config_found_relative_to_package(tmp_path: Path):
    """
    FI1: Config file found relative to package location

    GIVEN cloud_mirror package with cloud-mirror.toml in parent directory
    WHEN load_config() is called from that package
    THEN TOML config is found and loaded correctly
    """
    # Given: Package directory with TOML config in parent
    package_dir = tmp_path / "cloud_mirror"
    package_dir.mkdir()

    config_file = tmp_path / "cloud-mirror.toml"
    config_file.write_text("""
[defaults]
transfers = 32
keep_versions = 3

[profiles.test]
remote = "dropbox:test"
""")

    # When: Load config (with package_dir as context)
    config = load_config(package_dir=package_dir)

    # Then: Config loaded with defaults and profiles
    assert config["defaults"]["transfers"] == 32
    assert config["defaults"]["keep_versions"] == 3
    assert "test" in config["profiles"]
    assert config["profiles"]["test"]["remote"] == "dropbox:test"


def test_config_fallback_when_toml_missing(tmp_path: Path):
    """
    FI2: Config search fallback when TOML missing

    GIVEN package directory with NO cloud-mirror.toml
    WHEN load_config() is called
    THEN returns default config without error
    """
    # Given: Package directory without TOML
    package_dir = tmp_path / "cloud_mirror"
    package_dir.mkdir()

    # When: Load config
    config = load_config(package_dir=package_dir)

    # Then: Default config returned (no crash)
    assert isinstance(config, dict)
    assert config.get("defaults", {}) == {}
    assert config.get("profiles", {}) == {}


def test_malformed_toml_error_message(tmp_path: Path):
    """
    FI3: Malformed TOML produces clear error

    GIVEN cloud-mirror.toml with syntax error
    WHEN load_config() is called
    THEN raises exception with clear error message
    """
    # Given: Invalid TOML
    package_dir = tmp_path / "cloud_mirror"
    package_dir.mkdir()

    config_file = tmp_path / "cloud-mirror.toml"
    config_file.write_text("""
[defaults
missing_closing_bracket = true
""")

    # When/Then: Load raises exception with line number
    with pytest.raises(ConfigError, match=r"line \d+"):
        load_config(package_dir=package_dir)
