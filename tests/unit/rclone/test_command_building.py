"""
Tests for rclone command building (Story-32, Level 1).

Level 1 tests: Pure functions, no external dependencies.
Per ADR-001: No mocking, dependency injection only.

Test progression follows 4-part debuggability:
1. Named typical cases
2. Named edge cases
3. Systematic coverage (parametrized)
4. Property-based (if applicable)
"""

from dataclasses import dataclass
from pathlib import Path

import pytest

from cloud_mirror.rclone import (
    RcloneError,
    RcloneSyncConfig,
    build_rclone_command,
    filter_rclone_output,
    get_version_backup_path,
    parse_rclone_error,
    should_show_line,
)


# =============================================================================
# Part 0: Test Values (Named, Reusable, Type-Safe)
# =============================================================================


@dataclass(frozen=True)
class CommandTestCase:
    """Test case for command building."""

    name: str
    config: RcloneSyncConfig
    expected_contains: list[str]
    expected_not_contains: list[str] | None = None


@dataclass(frozen=True)
class ErrorTestCase:
    """Test case for error parsing."""

    name: str
    line: str
    expected_category: str | None
    expected_file: str | None = None


@dataclass(frozen=True)
class VerbosityTestCase:
    """Test case for output filtering."""

    name: str
    line: str
    verbosity: int
    expected_show: bool


# Command building test cases
COMMAND_TYPICAL: dict[str, CommandTestCase] = {
    "BASIC": CommandTestCase(
        name="basic sync command",
        config=RcloneSyncConfig(
            source=Path("/data/photos"),
            destination="dropbox:backup",
            config_path=Path("/etc/rclone.conf"),
        ),
        expected_contains=[
            "sync",
            "/data/photos/",
            "dropbox:backup",
            "--links",
            "--checksum",
            "--tpslimit",
            "--verbose",
        ],
    ),
    "WITH_VERSIONS": CommandTestCase(
        name="sync with version backup",
        config=RcloneSyncConfig(
            source=Path("/data/photos"),
            destination="dropbox:backup",
            config_path=Path("/etc/rclone.conf"),
            keep_versions=3,
            timestamp="2025-01-15T03-15-00Z",
        ),
        expected_contains=[
            "--backup-dir",
            # Sibling path: .versions is placed alongside destination, not inside
            "dropbox:.versions/backup/2025-01-15T03-15-00Z",
        ],
    ),
    "DRY_RUN": CommandTestCase(
        name="dry run mode",
        config=RcloneSyncConfig(
            source=Path("/data"),
            destination="remote:dest",
            config_path=Path("/etc/rclone.conf"),
            dry_run=True,
        ),
        expected_contains=["--dry-run"],
    ),
    "CUSTOM_LIMITS": CommandTestCase(
        name="custom transfer limits",
        config=RcloneSyncConfig(
            source=Path("/data"),
            destination="remote:dest",
            config_path=Path("/etc/rclone.conf"),
            transfers=32,
            checkers=16,
            tpslimit=8,
        ),
        expected_contains=[
            "--transfers", "32",
            "--checkers", "16",
            "--tpslimit", "8",
        ],
    ),
}

COMMAND_EDGES: dict[str, CommandTestCase] = {
    "ZERO_VERSIONS": CommandTestCase(
        name="zero versions means no backup-dir",
        config=RcloneSyncConfig(
            source=Path("/data"),
            destination="remote:dest",
            config_path=Path("/etc/rclone.conf"),
            keep_versions=0,
            timestamp="2025-01-15T03-15-00Z",
        ),
        expected_contains=["sync"],
        expected_not_contains=["--backup-dir"],
    ),
    "VERSIONS_NO_TIMESTAMP": CommandTestCase(
        name="versions without timestamp means no backup-dir",
        config=RcloneSyncConfig(
            source=Path("/data"),
            destination="remote:dest",
            config_path=Path("/etc/rclone.conf"),
            keep_versions=3,
            timestamp="",  # Empty timestamp
        ),
        expected_contains=["sync"],
        expected_not_contains=["--backup-dir"],
    ),
}

# Error parsing test cases
ERROR_TYPICAL: dict[str, ErrorTestCase] = {
    "RATE_LIMIT": ErrorTestCase(
        name="rate limit error",
        line="ERROR : too_many_write_operations: rate limit exceeded",
        expected_category="rate_limit",
    ),
    "AUTH_EXPIRED": ErrorTestCase(
        name="token expired error",
        line="ERROR : token expired: please re-authenticate",
        expected_category="auth_error",
    ),
    "FILE_TRANSFER": ErrorTestCase(
        name="file transfer error",
        line="ERROR : photos/image.jpg: Failed to copy: checksum mismatch",
        expected_category="transfer_error",
        expected_file="photos/image.jpg",
    ),
    "TIMEOUT": ErrorTestCase(
        name="timeout error",
        line="ERROR : operation timed out after 300s",
        expected_category="network_error",
    ),
}

ERROR_EDGES: dict[str, ErrorTestCase] = {
    "INFO_LINE": ErrorTestCase(
        name="info line is not an error",
        line="INFO  : photos/image.jpg: Copied (new)",
        expected_category=None,
    ),
    "MTIME_NOTICE": ErrorTestCase(
        name="modification time notice is not an error",
        line="NOTICE: Forced to upload files to set modification times",
        expected_category=None,
    ),
    "GENERIC_ERROR": ErrorTestCase(
        name="generic error without pattern",
        line="ERROR : Something went wrong",
        expected_category="unknown",
    ),
    "UNAUTHORIZED": ErrorTestCase(
        name="401 unauthorized",
        line="ERROR : failed to open: 401 Unauthorized",
        expected_category="auth_error",
    ),
}

# Verbosity test cases
VERBOSITY_TYPICAL: dict[str, VerbosityTestCase] = {
    "ERROR_AT_V0": VerbosityTestCase(
        name="errors shown at verbosity 0",
        line="ERROR: auth failed",
        verbosity=0,
        expected_show=True,
    ),
    "PROGRESS_AT_V1": VerbosityTestCase(
        name="progress shown at verbosity 1",
        line="INFO  : Transferred: 100 MiB",
        verbosity=1,
        expected_show=True,
    ),
    "FILE_HIDDEN_AT_V1": VerbosityTestCase(
        name="file transfers hidden at verbosity 1",
        line="INFO  : photo.jpg: Copied (new)",
        verbosity=1,
        expected_show=False,
    ),
    "FILE_SHOWN_AT_V2": VerbosityTestCase(
        name="file transfers shown at verbosity 2",
        line="INFO  : photo.jpg: Copied (new)",
        verbosity=2,
        expected_show=True,
    ),
}

VERBOSITY_EDGES: dict[str, VerbosityTestCase] = {
    "NOTICE_AT_V0": VerbosityTestCase(
        name="notices shown at verbosity 0",
        line="NOTICE: Rate limit reached",
        verbosity=0,
        expected_show=True,
    ),
    "MTIME_NOTICE_HIDDEN": VerbosityTestCase(
        name="mtime notice hidden even at high verbosity",
        line="NOTICE: Forced to upload files to set modification times on Dropbox",
        verbosity=2,
        expected_show=False,
    ),
    "IDENTICAL_HIDDEN_AT_V1": VerbosityTestCase(
        name="identical files hidden at verbosity 1",
        line="INFO  : photo.jpg: src and dst identical",
        verbosity=1,
        expected_show=False,
    ),
    "DELETED_HIDDEN_AT_V1": VerbosityTestCase(
        name="deleted files hidden at verbosity 1",
        line="INFO  : old.txt: Deleted",
        verbosity=1,
        expected_show=False,
    ),
}


# =============================================================================
# Part 1: Named Typical Cases (One Test Per Category)
# =============================================================================


class TestBuildRcloneCommandTypical:
    """GIVEN typical sync configurations."""

    def test_basic_sync_command(self) -> None:
        """WHEN building basic command THEN includes required flags."""
        case = COMMAND_TYPICAL["BASIC"]
        cmd = build_rclone_command(case.config)
        cmd_str = " ".join(cmd)

        for expected in case.expected_contains:
            assert expected in cmd_str, f"Missing: {expected}"

    def test_with_version_backup(self) -> None:
        """WHEN versioning enabled THEN includes backup-dir."""
        case = COMMAND_TYPICAL["WITH_VERSIONS"]
        cmd = build_rclone_command(case.config)
        cmd_str = " ".join(cmd)

        for expected in case.expected_contains:
            assert expected in cmd_str, f"Missing: {expected}"

    def test_dry_run_mode(self) -> None:
        """WHEN dry run THEN includes --dry-run flag."""
        case = COMMAND_TYPICAL["DRY_RUN"]
        cmd = build_rclone_command(case.config)

        assert "--dry-run" in cmd

    def test_custom_limits(self) -> None:
        """WHEN custom limits THEN command uses them."""
        case = COMMAND_TYPICAL["CUSTOM_LIMITS"]
        cmd = build_rclone_command(case.config)
        cmd_str = " ".join(cmd)

        assert "--transfers" in cmd_str
        assert "32" in cmd_str
        assert "--tpslimit" in cmd_str
        assert "8" in cmd_str


class TestParseRcloneErrorTypical:
    """GIVEN typical rclone error outputs."""

    def test_rate_limit_error(self) -> None:
        """WHEN parsing rate limit THEN returns rate_limit category."""
        case = ERROR_TYPICAL["RATE_LIMIT"]
        result = parse_rclone_error(case.line)

        assert result is not None
        assert result.category == case.expected_category

    def test_auth_expired_error(self) -> None:
        """WHEN parsing expired token THEN returns auth_error category."""
        case = ERROR_TYPICAL["AUTH_EXPIRED"]
        result = parse_rclone_error(case.line)

        assert result is not None
        assert result.category == case.expected_category

    def test_file_transfer_error(self) -> None:
        """WHEN parsing file error THEN extracts file path."""
        case = ERROR_TYPICAL["FILE_TRANSFER"]
        result = parse_rclone_error(case.line)

        assert result is not None
        assert result.category == case.expected_category
        assert result.file == case.expected_file

    def test_timeout_error(self) -> None:
        """WHEN parsing timeout THEN returns network_error category."""
        case = ERROR_TYPICAL["TIMEOUT"]
        result = parse_rclone_error(case.line)

        assert result is not None
        assert result.category == case.expected_category


class TestFilterOutputTypical:
    """GIVEN typical rclone output lines."""

    def test_errors_shown_at_v0(self) -> None:
        """WHEN verbosity 0 THEN errors are shown."""
        case = VERBOSITY_TYPICAL["ERROR_AT_V0"]
        result = should_show_line(case.line, case.verbosity)

        assert result == case.expected_show

    def test_progress_shown_at_v1(self) -> None:
        """WHEN verbosity 1 THEN progress is shown."""
        case = VERBOSITY_TYPICAL["PROGRESS_AT_V1"]
        result = should_show_line(case.line, case.verbosity)

        assert result == case.expected_show

    def test_files_hidden_at_v1(self) -> None:
        """WHEN verbosity 1 THEN file transfers are hidden."""
        case = VERBOSITY_TYPICAL["FILE_HIDDEN_AT_V1"]
        result = should_show_line(case.line, case.verbosity)

        assert result == case.expected_show

    def test_files_shown_at_v2(self) -> None:
        """WHEN verbosity 2 THEN file transfers are shown."""
        case = VERBOSITY_TYPICAL["FILE_SHOWN_AT_V2"]
        result = should_show_line(case.line, case.verbosity)

        assert result == case.expected_show


# =============================================================================
# Part 2: Named Edge Cases (One Test Per Boundary)
# =============================================================================


class TestBuildRcloneCommandEdges:
    """GIVEN edge case configurations."""

    def test_zero_versions_no_backup(self) -> None:
        """WHEN keep_versions=0 THEN no backup-dir flag."""
        case = COMMAND_EDGES["ZERO_VERSIONS"]
        cmd = build_rclone_command(case.config)
        cmd_str = " ".join(cmd)

        assert "--backup-dir" not in cmd_str

    def test_versions_without_timestamp(self) -> None:
        """WHEN timestamp empty THEN no backup-dir flag."""
        case = COMMAND_EDGES["VERSIONS_NO_TIMESTAMP"]
        cmd = build_rclone_command(case.config)
        cmd_str = " ".join(cmd)

        assert "--backup-dir" not in cmd_str


class TestParseRcloneErrorEdges:
    """GIVEN edge case error lines."""

    def test_info_line_not_error(self) -> None:
        """WHEN parsing INFO line THEN returns None."""
        case = ERROR_EDGES["INFO_LINE"]
        result = parse_rclone_error(case.line)

        assert result is None

    def test_mtime_notice_not_error(self) -> None:
        """WHEN parsing mtime notice THEN returns None."""
        case = ERROR_EDGES["MTIME_NOTICE"]
        result = parse_rclone_error(case.line)

        assert result is None

    def test_generic_error(self) -> None:
        """WHEN parsing unrecognized error THEN returns unknown category."""
        case = ERROR_EDGES["GENERIC_ERROR"]
        result = parse_rclone_error(case.line)

        assert result is not None
        assert result.category == "unknown"

    def test_unauthorized_401(self) -> None:
        """WHEN parsing 401 THEN returns auth_error category."""
        case = ERROR_EDGES["UNAUTHORIZED"]
        result = parse_rclone_error(case.line)

        assert result is not None
        assert result.category == "auth_error"


class TestFilterOutputEdges:
    """GIVEN edge case output lines."""

    def test_notices_shown_at_v0(self) -> None:
        """WHEN verbosity 0 THEN notices are shown."""
        case = VERBOSITY_EDGES["NOTICE_AT_V0"]
        result = should_show_line(case.line, case.verbosity)

        assert result == case.expected_show

    def test_mtime_notice_always_hidden(self) -> None:
        """WHEN mtime notice THEN always hidden."""
        case = VERBOSITY_EDGES["MTIME_NOTICE_HIDDEN"]
        result = should_show_line(case.line, case.verbosity)

        assert result == case.expected_show

    def test_identical_hidden_at_v1(self) -> None:
        """WHEN identical files at v1 THEN hidden."""
        case = VERBOSITY_EDGES["IDENTICAL_HIDDEN_AT_V1"]
        result = should_show_line(case.line, case.verbosity)

        assert result == case.expected_show

    def test_deleted_hidden_at_v1(self) -> None:
        """WHEN deleted files at v1 THEN hidden."""
        case = VERBOSITY_EDGES["DELETED_HIDDEN_AT_V1"]
        result = should_show_line(case.line, case.verbosity)

        assert result == case.expected_show


# =============================================================================
# Part 3: Systematic Coverage (Parametrized)
# =============================================================================


class TestSystematicCoverage:
    """GIVEN all known test cases."""

    @pytest.mark.parametrize(
        ("name", "case"),
        list(COMMAND_TYPICAL.items()) + list(COMMAND_EDGES.items()),
    )
    def test_all_command_cases(self, name: str, case: CommandTestCase) -> None:
        """WHEN testing all command cases THEN all pass."""
        cmd = build_rclone_command(case.config)
        cmd_str = " ".join(cmd)

        for expected in case.expected_contains:
            assert expected in cmd_str, f"[{name}] Missing: {expected}"

        if case.expected_not_contains:
            for not_expected in case.expected_not_contains:
                assert not_expected not in cmd_str, f"[{name}] Unexpected: {not_expected}"

    @pytest.mark.parametrize(
        ("name", "case"),
        list(ERROR_TYPICAL.items()) + list(ERROR_EDGES.items()),
    )
    def test_all_error_cases(self, name: str, case: ErrorTestCase) -> None:
        """WHEN testing all error cases THEN all pass."""
        result = parse_rclone_error(case.line)

        if case.expected_category is None:
            assert result is None, f"[{name}] Expected None, got {result}"
        else:
            assert result is not None, f"[{name}] Expected error, got None"
            assert result.category == case.expected_category, \
                f"[{name}] Expected {case.expected_category}, got {result.category}"

            if case.expected_file:
                assert result.file == case.expected_file, \
                    f"[{name}] Expected file {case.expected_file}, got {result.file}"

    @pytest.mark.parametrize(
        ("name", "case"),
        list(VERBOSITY_TYPICAL.items()) + list(VERBOSITY_EDGES.items()),
    )
    def test_all_verbosity_cases(self, name: str, case: VerbosityTestCase) -> None:
        """WHEN testing all verbosity cases THEN all pass."""
        result = should_show_line(case.line, case.verbosity)

        assert result == case.expected_show, \
            f"[{name}] Expected {case.expected_show}, got {result}"


# =============================================================================
# Additional Tests: Helper Functions
# =============================================================================


class TestGetVersionBackupPath:
    """Tests for get_version_backup_path function.

    The version backup path is a SIBLING to the destination, not inside it.
    This avoids rclone's restriction that --backup-dir cannot overlap with destination.
    """

    def test_constructs_path_correctly(self) -> None:
        """GIVEN destination and timestamp WHEN called THEN returns sibling path."""
        result = get_version_backup_path("dropbox:backup", "2025-01-15T03-15-00Z")

        # .versions is at root level, with destination name as subfolder
        assert result == "dropbox:.versions/backup/2025-01-15T03-15-00Z"

    def test_works_with_nested_destination(self) -> None:
        """GIVEN nested destination WHEN called THEN returns sibling path."""
        result = get_version_backup_path("dropbox:my/nested/backup", "2025-01-15T03-15-00Z")

        # .versions is placed alongside "backup", not inside it
        assert result == "dropbox:my/nested/.versions/backup/2025-01-15T03-15-00Z"


class TestFilterRcloneOutput:
    """Tests for filter_rclone_output function."""

    def test_filters_multiple_lines(self) -> None:
        """GIVEN multiple lines WHEN filtering THEN returns correct subset."""
        lines = [
            "ERROR: auth failed",
            "INFO  : photo.jpg: Copied (new)",
            "INFO  : Transferred: 100 MiB",
            "NOTICE: Rate limit reached",
        ]

        # At verbosity 0, only errors and notices
        result = filter_rclone_output(lines, verbosity=0)
        assert len(result) == 2
        assert "ERROR" in result[0]
        assert "NOTICE" in result[1]

    def test_returns_all_at_v2(self) -> None:
        """GIVEN lines WHEN verbosity 2 THEN returns all."""
        lines = [
            "ERROR: auth failed",
            "INFO  : photo.jpg: Copied (new)",
            "INFO  : Transferred: 100 MiB",
        ]

        result = filter_rclone_output(lines, verbosity=2)
        assert len(result) == 3


class TestRcloneErrorDataclass:
    """Tests for RcloneError dataclass."""

    def test_is_frozen(self) -> None:
        """GIVEN RcloneError WHEN modifying THEN raises error."""
        error = RcloneError(category="rate_limit", message="test")

        with pytest.raises(AttributeError):
            error.category = "other"  # type: ignore[assignment]

    def test_equality(self) -> None:
        """GIVEN two identical errors WHEN comparing THEN equal."""
        error1 = RcloneError(category="rate_limit", message="test")
        error2 = RcloneError(category="rate_limit", message="test")

        assert error1 == error2
