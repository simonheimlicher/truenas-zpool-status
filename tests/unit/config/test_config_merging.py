"""Unit tests for config merging functionality.

Tests verify that merge_config() correctly applies precedence order:
defaults → profile → CLI args (where later layers override earlier layers).
"""

import pytest
from typing import Any
from cloud_mirror.config import merge_config


class TestTypicalInputs:
    """Tests with typical, expected inputs."""

    def test_merge_defaults_and_profile(self):
        """
        GIVEN defaults with transfers=32
        AND profile with remote='dropbox:photos'
        WHEN merge_config() is called
        THEN returns merged config with both settings
        """
        # Given
        defaults = {"transfers": 32, "keep_versions": 3}
        profile = {"remote": "dropbox:photos"}
        cli_args: dict[str, Any] = {}

        # When
        result = merge_config(defaults, profile, cli_args)

        # Then
        assert result["transfers"] == 32
        assert result["keep_versions"] == 3
        assert result["remote"] == "dropbox:photos"

    def test_profile_overrides_defaults(self):
        """
        GIVEN defaults with transfers=32
        AND profile with transfers=64
        WHEN merge_config() is called
        THEN profile value takes precedence
        """
        # Given
        defaults = {"transfers": 32}
        profile = {"transfers": 64}
        cli_args: dict[str, Any] = {}

        # When
        result = merge_config(defaults, profile, cli_args)

        # Then
        assert result["transfers"] == 64

    def test_cli_overrides_profile(self):
        """
        GIVEN profile with remote='dropbox:photos'
        AND CLI args with remote='b2:backup'
        WHEN merge_config() is called
        THEN CLI value takes precedence
        """
        # Given
        defaults: dict[str, Any] = {}
        profile = {"remote": "dropbox:photos"}
        cli_args = {"remote": "b2:backup"}

        # When
        result = merge_config(defaults, profile, cli_args)

        # Then
        assert result["remote"] == "b2:backup"

    def test_cli_overrides_both_defaults_and_profile(self):
        """
        GIVEN defaults with transfers=32
        AND profile with transfers=64
        AND CLI args with transfers=128
        WHEN merge_config() is called
        THEN CLI value takes precedence over both
        """
        # Given
        defaults = {"transfers": 32}
        profile = {"transfers": 64}
        cli_args = {"transfers": 128}

        # When
        result = merge_config(defaults, profile, cli_args)

        # Then
        assert result["transfers"] == 128


class TestPartialProfiles:
    """Tests with partial profile specifications (source-only or destination-only)."""

    def test_partial_profile_with_source_only(self):
        """
        GIVEN profile with source='tank/photos' (no destination)
        AND CLI args with destination='dropbox:backup'
        WHEN merge_config() is called
        THEN returns config with both source and destination
        """
        # Given
        defaults: dict[str, Any] = {}
        profile = {"source": "tank/photos", "transfers": 64}
        cli_args = {"destination": "dropbox:backup"}

        # When
        result = merge_config(defaults, profile, cli_args)

        # Then
        assert result["source"] == "tank/photos"
        assert result["destination"] == "dropbox:backup"
        assert result["transfers"] == 64

    def test_partial_profile_with_destination_only(self):
        """
        GIVEN profile with destination='dropbox:photos' (no source)
        AND CLI args with source='tank/photos'
        WHEN merge_config() is called
        THEN returns config with both source and destination
        """
        # Given
        defaults: dict[str, Any] = {}
        profile = {"destination": "dropbox:photos", "keep_versions": 5}
        cli_args = {"source": "tank/photos"}

        # When
        result = merge_config(defaults, profile, cli_args)

        # Then
        assert result["source"] == "tank/photos"
        assert result["destination"] == "dropbox:photos"
        assert result["keep_versions"] == 5


class TestEdgeCases:
    """Tests with edge cases and error conditions."""

    def test_empty_inputs_returns_empty_config(self):
        """
        GIVEN all empty dicts
        WHEN merge_config() is called
        THEN returns empty config
        """
        # Given
        defaults: dict[str, Any] = {}
        profile: dict[str, Any] = {}
        cli_args: dict[str, Any] = {}

        # When
        result = merge_config(defaults, profile, cli_args)

        # Then
        assert result == {}

    def test_none_profile_handled_gracefully(self):
        """
        GIVEN defaults and CLI args, but None for profile
        WHEN merge_config() is called
        THEN merges defaults and CLI without error
        """
        # Given
        defaults = {"transfers": 32}
        profile = None
        cli_args = {"remote": "dropbox:backup"}

        # When
        result = merge_config(defaults, profile, cli_args)

        # Then
        assert result["transfers"] == 32
        assert result["remote"] == "dropbox:backup"
