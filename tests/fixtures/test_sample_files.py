"""
Tests for sample files pytest fixture (graduated from Feature-54, Story-54).

These tests verify the sample_files_in_tmp fixture creates the expected test files.
No VM required - runs on macOS host.

Tests are ordered trivial → complex for fast failure on fixture issues.
"""

from pathlib import Path


class TestSampleFilesFixture:
    """Tests for sample_files_in_tmp fixture (FR1: sample file creation)."""

    def test_fixture_creates_file1(self, sample_files_in_tmp: Path) -> None:
        """Fixture should create file1.txt with known content."""
        file1 = sample_files_in_tmp / "file1.txt"
        assert file1.exists(), "file1.txt should exist"
        assert file1.read_text() == "content of file 1\n"

    def test_fixture_creates_subdir_with_file2(
        self, sample_files_in_tmp: Path
    ) -> None:
        """Fixture should create subdir/file2.txt with known content."""
        subdir = sample_files_in_tmp / "subdir"
        assert subdir.is_dir(), "subdir should be a directory"

        file2 = subdir / "file2.txt"
        assert file2.exists(), "subdir/file2.txt should exist"
        assert file2.read_text() == "content of file 2\n"

    def test_fixture_creates_symlink(self, sample_files_in_tmp: Path) -> None:
        """Fixture should create symlink.txt pointing to file1.txt."""
        symlink = sample_files_in_tmp / "symlink.txt"
        assert symlink.is_symlink(), "symlink.txt should be a symlink"
        assert symlink.resolve().name == "file1.txt"

    def test_symlink_is_readable(self, sample_files_in_tmp: Path) -> None:
        """Symlink should be readable and return file1.txt content."""
        symlink = sample_files_in_tmp / "symlink.txt"
        assert symlink.read_text() == "content of file 1\n"
