"""Unit tests for TOML parsing functionality.

Tests follow debuggability-first organization:
1. Named typical cases
2. Named edge cases
3. Systematic coverage (parametrized)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cloud_mirror.config import ConfigError, parse_toml


class TestTypicalInputs:
    """Test parsing of typical, well-formed TOML configurations."""

    def test_parse_toml_with_defaults_section(self, tmp_path: Path) -> None:
        """
        GIVEN cloud-mirror.toml with [defaults] section
        WHEN parse_toml() is called
        THEN returns dict with defaults key containing parsed values
        """
        # Given
        config_file = tmp_path / "cloud-mirror.toml"
        config_file.write_text("""
[defaults]
transfers = 64
keep_versions = 3
""")

        # When
        config = parse_toml(config_file)

        # Then
        assert "defaults" in config
        assert config["defaults"]["transfers"] == 64
        assert config["defaults"]["keep_versions"] == 3

    def test_parse_toml_with_single_profile(self, tmp_path: Path) -> None:
        """
        GIVEN cloud-mirror.toml with one profile
        WHEN parse_toml() is called
        THEN returns dict with profiles key containing the profile
        """
        # Given
        config_file = tmp_path / "cloud-mirror.toml"
        config_file.write_text("""
[profiles.photos]
remote = "dropbox:photos"
keep_versions = 5
""")

        # When
        config = parse_toml(config_file)

        # Then
        assert "profiles" in config
        assert "photos" in config["profiles"]
        assert config["profiles"]["photos"]["remote"] == "dropbox:photos"
        assert config["profiles"]["photos"]["keep_versions"] == 5

    def test_parse_toml_with_defaults_and_profiles(self, tmp_path: Path) -> None:
        """
        GIVEN cloud-mirror.toml with [defaults] and [profiles.*] sections
        WHEN parse_toml() is called
        THEN returns dict with both sections populated
        """
        # Given
        config_file = tmp_path / "cloud-mirror.toml"
        config_file.write_text("""
[defaults]
transfers = 64
tpslimit = 12

[profiles.photos]
remote = "dropbox:photos"

[profiles.docs]
source = "tank/documents"
destination = "dropbox:docs"
""")

        # When
        config = parse_toml(config_file)

        # Then
        assert config["defaults"]["transfers"] == 64
        assert config["defaults"]["tpslimit"] == 12
        assert len(config["profiles"]) == 2
        assert config["profiles"]["photos"]["remote"] == "dropbox:photos"
        assert config["profiles"]["docs"]["source"] == "tank/documents"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_parse_toml_empty_file_returns_empty_structure(
        self, tmp_path: Path
    ) -> None:
        """
        GIVEN empty TOML file
        WHEN parse_toml() is called
        THEN returns dict with empty defaults and profiles
        """
        # Given
        config_file = tmp_path / "empty.toml"
        config_file.write_text("")

        # When
        config = parse_toml(config_file)

        # Then
        assert config["defaults"] == {}
        assert config["profiles"] == {}

    def test_parse_toml_malformed_raises_config_error(self, tmp_path: Path) -> None:
        """
        GIVEN TOML file with syntax error (missing closing bracket)
        WHEN parse_toml() is called
        THEN raises ConfigError with line number in message
        """
        # Given
        config_file = tmp_path / "bad.toml"
        config_file.write_text("""
[defaults
missing_closing_bracket = true
""")

        # When/Then
        with pytest.raises(ConfigError, match=r"line \d+"):
            parse_toml(config_file)

    def test_parse_toml_invalid_value_raises_config_error(self, tmp_path: Path) -> None:
        """
        GIVEN TOML file with invalid value syntax
        WHEN parse_toml() is called
        THEN raises ConfigError with clear error message
        """
        # Given
        config_file = tmp_path / "invalid.toml"
        config_file.write_text("""
[defaults]
transfers = "not a number expected by TOML parser"
keep_versions = {invalid dict syntax
""")

        # When/Then
        with pytest.raises(ConfigError):
            parse_toml(config_file)

    def test_parse_toml_file_not_found_raises_config_error(
        self, tmp_path: Path
    ) -> None:
        """
        GIVEN path to non-existent TOML file
        WHEN parse_toml() is called
        THEN raises ConfigError with actionable message
        """
        # Given
        config_file = tmp_path / "does-not-exist.toml"

        # When/Then
        with pytest.raises(ConfigError, match="not found"):
            parse_toml(config_file)

    def test_parse_toml_with_rclone_section(self, tmp_path: Path) -> None:
        """
        GIVEN TOML with [rclone] section for rclone config path
        WHEN parse_toml() is called
        THEN rclone section is included in parsed config
        """
        # Given
        config_file = tmp_path / "cloud-mirror.toml"
        config_file.write_text("""
[rclone]
config = "./rclone.conf"

[defaults]
transfers = 32
""")

        # When
        config = parse_toml(config_file)

        # Then
        assert "rclone" in config
        assert config["rclone"]["config"] == "./rclone.conf"


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("defaults", "transfers", 64),
        ("defaults", "tpslimit", 12),
        ("defaults", "keep_versions", 3),
    ],
)
def test_parse_toml_typical_default_values(
    tmp_path: Path, section: str, key: str, value: int
) -> None:
    """
    Systematic coverage: Verify parsing of common default configuration values.

    GIVEN TOML file with a default configuration value
    WHEN parse_toml() is called
    THEN the value is correctly parsed
    """
    # Given
    config_file = tmp_path / "config.toml"
    config_file.write_text(f"""
[{section}]
{key} = {value}
""")

    # When
    config = parse_toml(config_file)

    # Then
    assert config[section][key] == value
