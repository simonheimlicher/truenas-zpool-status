"""
Level 1 Unit Tests: CLI Argument Parsing.

Tests for cloud_mirror.cli module - pure argparse logic, no external dependencies.

Test Levels:
- Level 1 (Unit): All tests in this file - pure Python argparse logic
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest


# =============================================================================
# Part 0: Shared Test Values
# =============================================================================


@dataclass(frozen=True)
class ParseTestCase:
    """Test case for argument parsing."""

    name: str
    args: list[str]
    expected_dataset: str | None = None
    expected_destination: str | None = None
    expected_keep_versions: int = 0
    expected_keep_snapshot: bool = False
    expected_keep_clone: bool = False
    expected_transfers: int = 64
    expected_tpslimit: int = 12
    expected_dry_run: bool = False
    expected_config: Path | None = None
    expected_verbose: int = 0


PARSE_TYPICAL: dict[str, ParseTestCase] = {
    "BASIC": ParseTestCase(
        name="basic positional arguments",
        args=["push", "testpool/data", "dropbox:backup"],
        expected_dataset="testpool/data",
        expected_destination="dropbox:backup",
    ),
    "WITH_OPTIONS": ParseTestCase(
        name="with all options",
        args=[
            "push",
            "tank/photos",
            "remote:archive",
            "--keep-versions",
            "5",
            "--keep-snapshot",
            "--keep-clone",
            "--transfers",
            "32",
            "--tpslimit",
            "8",
            "--dry-run",
        ],
        expected_dataset="tank/photos",
        expected_destination="remote:archive",
        expected_keep_versions=5,
        expected_keep_snapshot=True,
        expected_keep_clone=True,
        expected_transfers=32,
        expected_tpslimit=8,
        expected_dry_run=True,
    ),
    "WITH_CONFIG": ParseTestCase(
        name="with config file",
        args=["push", "pool/data", "remote:dest", "--config", "/path/to/rclone.conf"],
        expected_dataset="pool/data",
        expected_destination="remote:dest",
        expected_config=Path("/path/to/rclone.conf"),
    ),
    "VERBOSE_1": ParseTestCase(
        name="single verbose flag",
        args=["push", "pool/data", "remote:dest", "-v"],
        expected_dataset="pool/data",
        expected_destination="remote:dest",
        expected_verbose=1,
    ),
    "VERBOSE_2": ParseTestCase(
        name="double verbose flag",
        args=["push", "pool/data", "remote:dest", "-vv"],
        expected_dataset="pool/data",
        expected_destination="remote:dest",
        expected_verbose=2,
    ),
    "VERBOSE_3": ParseTestCase(
        name="triple verbose flag",
        args=["push", "pool/data", "remote:dest", "-vvv"],
        expected_dataset="pool/data",
        expected_destination="remote:dest",
        expected_verbose=3,
    ),
}

PARSE_EDGES: dict[str, ParseTestCase] = {
    "NESTED_DATASET": ParseTestCase(
        name="deeply nested dataset",
        args=["push", "pool/data/photos/2024/vacation", "dropbox:backup/archive"],
        expected_dataset="pool/data/photos/2024/vacation",
        expected_destination="dropbox:backup/archive",
    ),
    "ROOT_POOL": ParseTestCase(
        name="root pool without path",
        args=["push", "testpool", "remote:dest"],
        expected_dataset="testpool",
        expected_destination="remote:dest",
    ),
    "ZERO_VERSIONS": ParseTestCase(
        name="explicit zero versions",
        args=["push", "pool/data", "remote:dest", "--keep-versions", "0"],
        expected_dataset="pool/data",
        expected_destination="remote:dest",
        expected_keep_versions=0,
    ),
}


# =============================================================================
# Part 1: Named Typical Cases
# =============================================================================


class TestParseTypical:
    """GIVEN typical CLI invocations."""

    def test_basic_positional_arguments(self) -> None:
        """FR1: WHEN push with dataset and destination THEN parsed correctly."""
        from cloud_mirror.cli import parse_args

        case = PARSE_TYPICAL["BASIC"]
        args = parse_args(case.args)

        assert args.dataset == case.expected_dataset
        assert args.destination == case.expected_destination

    def test_with_all_options(self) -> None:
        """FR2: WHEN push with all options THEN all parsed correctly."""
        from cloud_mirror.cli import parse_args

        case = PARSE_TYPICAL["WITH_OPTIONS"]
        args = parse_args(case.args)

        assert args.dataset == case.expected_dataset
        assert args.destination == case.expected_destination
        assert args.keep_versions == case.expected_keep_versions
        assert args.keep_snapshot == case.expected_keep_snapshot
        assert args.keep_clone == case.expected_keep_clone
        assert args.transfers == case.expected_transfers
        assert args.tpslimit == case.expected_tpslimit
        assert args.dry_run == case.expected_dry_run

    def test_with_config_file(self) -> None:
        """FR2: WHEN --config provided THEN path parsed as Path."""
        from cloud_mirror.cli import parse_args

        case = PARSE_TYPICAL["WITH_CONFIG"]
        args = parse_args(case.args)

        assert args.config == case.expected_config

    def test_verbose_level_1(self) -> None:
        """FR3: WHEN -v flag THEN verbose=1."""
        from cloud_mirror.cli import parse_args

        case = PARSE_TYPICAL["VERBOSE_1"]
        args = parse_args(case.args)

        assert args.verbose == case.expected_verbose

    def test_verbose_level_2(self) -> None:
        """FR3: WHEN -vv flag THEN verbose=2."""
        from cloud_mirror.cli import parse_args

        case = PARSE_TYPICAL["VERBOSE_2"]
        args = parse_args(case.args)

        assert args.verbose == case.expected_verbose

    def test_verbose_level_3(self) -> None:
        """FR3: WHEN -vvv flag THEN verbose=3."""
        from cloud_mirror.cli import parse_args

        case = PARSE_TYPICAL["VERBOSE_3"]
        args = parse_args(case.args)

        assert args.verbose == case.expected_verbose


# =============================================================================
# Part 2: Named Edge Cases
# =============================================================================


class TestParseEdges:
    """GIVEN boundary conditions."""

    def test_nested_dataset_path(self) -> None:
        """WHEN deeply nested dataset THEN parsed correctly."""
        from cloud_mirror.cli import parse_args

        case = PARSE_EDGES["NESTED_DATASET"]
        args = parse_args(case.args)

        assert args.dataset == case.expected_dataset
        assert args.destination == case.expected_destination

    def test_root_pool_without_path(self) -> None:
        """WHEN root pool only THEN parsed correctly."""
        from cloud_mirror.cli import parse_args

        case = PARSE_EDGES["ROOT_POOL"]
        args = parse_args(case.args)

        assert args.dataset == case.expected_dataset

    def test_explicit_zero_versions(self) -> None:
        """WHEN --keep-versions 0 THEN defaults preserved."""
        from cloud_mirror.cli import parse_args

        case = PARSE_EDGES["ZERO_VERSIONS"]
        args = parse_args(case.args)

        assert args.keep_versions == 0


class TestParseDefaults:
    """GIVEN minimal arguments."""

    def test_default_keep_versions(self) -> None:
        """Default keep_versions is 0."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["push", "pool/data", "remote:dest"])
        assert args.keep_versions == 0

    def test_default_keep_snapshot_is_false(self) -> None:
        """Default keep_snapshot is False."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["push", "pool/data", "remote:dest"])
        assert args.keep_snapshot is False

    def test_default_keep_clone_is_false(self) -> None:
        """Default keep_clone is False."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["push", "pool/data", "remote:dest"])
        assert args.keep_clone is False

    def test_default_transfers(self) -> None:
        """Default transfers is 64."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["push", "pool/data", "remote:dest"])
        assert args.transfers == 64

    def test_default_tpslimit(self) -> None:
        """Default tpslimit is 12."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["push", "pool/data", "remote:dest"])
        assert args.tpslimit == 12

    def test_default_dry_run_is_false(self) -> None:
        """Default dry_run is False."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["push", "pool/data", "remote:dest"])
        assert args.dry_run is False

    def test_default_config_is_none(self) -> None:
        """Default config is None."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["push", "pool/data", "remote:dest"])
        assert args.config is None

    def test_default_verbose_is_zero(self) -> None:
        """Default verbose is 0."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["push", "pool/data", "remote:dest"])
        assert args.verbose == 0


class TestParseErrors:
    """GIVEN invalid arguments."""

    def test_missing_dataset_raises(self) -> None:
        """WHEN no dataset provided THEN raises SystemExit."""
        from cloud_mirror.cli import parse_args

        with pytest.raises(SystemExit):
            parse_args(["push"])

    def test_missing_destination_raises(self) -> None:
        """WHEN no destination provided THEN raises SystemExit."""
        from cloud_mirror.cli import parse_args

        with pytest.raises(SystemExit):
            parse_args(["push", "pool/data"])

    def test_invalid_keep_versions_raises(self) -> None:
        """WHEN --keep-versions is negative THEN raises SystemExit."""
        from cloud_mirror.cli import parse_args

        with pytest.raises(SystemExit):
            parse_args(["push", "pool/data", "remote:dest", "--keep-versions", "-1"])

    def test_invalid_transfers_raises(self) -> None:
        """WHEN --transfers is not a number THEN raises SystemExit."""
        from cloud_mirror.cli import parse_args

        with pytest.raises(SystemExit):
            parse_args(["push", "pool/data", "remote:dest", "--transfers", "abc"])


# =============================================================================
# Part 3: Systematic Coverage
# =============================================================================


class TestSystematicCoverage:
    """GIVEN all known cases."""

    @pytest.mark.parametrize(
        ("name", "case"),
        list(PARSE_TYPICAL.items()) + list(PARSE_EDGES.items()),
    )
    def test_all_cases_parse_successfully(self, name: str, case: ParseTestCase) -> None:
        """WHEN testing all known cases THEN all parse without error."""
        from cloud_mirror.cli import parse_args

        args = parse_args(case.args)

        assert args.dataset == case.expected_dataset
        assert args.destination == case.expected_destination


# =============================================================================
# Additional Tests: Help and Subcommand Structure
# =============================================================================


class TestHelpAndStructure:
    """FR4: Test help and command structure."""

    def test_help_exits_zero(self) -> None:
        """WHEN --help THEN exits with code 0."""
        from cloud_mirror.cli import parse_args

        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--help"])

        assert exc_info.value.code == 0

    def test_push_help_exits_zero(self) -> None:
        """WHEN push --help THEN exits with code 0."""
        from cloud_mirror.cli import parse_args

        with pytest.raises(SystemExit) as exc_info:
            parse_args(["push", "--help"])

        assert exc_info.value.code == 0

    def test_command_is_push(self) -> None:
        """WHEN push subcommand THEN command='push'."""
        from cloud_mirror.cli import parse_args

        args = parse_args(["push", "pool/data", "remote:dest"])

        assert args.command == "push"
