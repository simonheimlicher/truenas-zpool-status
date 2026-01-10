"""Unit tests for CLI --profile argument parsing."""

import pytest

from cloud_mirror.cli import parse_args


def test_parse_args_with_profile_flag() -> None:
    """
    GIVEN cloud-mirror CLI with --profile flag
    WHEN parsing args: ["--profile", "photos", "src", "dest"]
    THEN parsed.profile == "photos"
    """
    # When
    args = parse_args(["--profile", "photos", "src", "dest"])

    # Then
    assert args.profile == "photos"
    assert args.source == "src"
    assert args.destination == "dest"


def test_parse_args_profile_with_optional_positionals() -> None:
    """
    GIVEN --profile flag without positional arguments
    WHEN parsing args: ["--profile", "backup"]
    THEN parsed.profile == "backup"
    AND parsed.source is None
    AND parsed.destination is None
    """
    # When
    args = parse_args(["--profile", "backup"])

    # Then
    assert args.profile == "backup"
    assert args.source is None
    assert args.destination is None


def test_parse_args_positionals_without_profile() -> None:
    """
    GIVEN positional args without --profile
    WHEN parsing args: ["testpool/data", "dropbox:backup"]
    THEN positionals parsed normally
    AND parsed.profile is None
    """
    # When
    args = parse_args(["testpool/data", "dropbox:backup"])

    # Then
    assert args.source == "testpool/data"
    assert args.destination == "dropbox:backup"
    assert args.profile is None


def test_parse_args_partial_positionals_with_profile() -> None:
    """
    GIVEN --profile with only source positional
    WHEN parsing args: ["testpool/photos", "--profile", "backup"]
    THEN source from positional, destination from profile (merged in main)
    """
    # When
    args = parse_args(["testpool/photos", "--profile", "backup"])

    # Then
    assert args.source == "testpool/photos"
    assert args.destination is None  # Will be filled from profile in main()
    assert args.profile == "backup"
