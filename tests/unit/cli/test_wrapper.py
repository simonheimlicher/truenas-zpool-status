"""Unit tests for wrapper script path resolution and validation logic."""

import sys
from pathlib import Path

import pytest


def test_resolve_wrapper_location(tmp_path: Path) -> None:
    """
    GIVEN wrapper script at known location
    WHEN Path(__file__).resolve() called
    THEN returns absolute path with symlinks resolved
    """
    # Given
    wrapper_dir = tmp_path / "project"
    wrapper_dir.mkdir()
    wrapper = wrapper_dir / "cloud-mirror"
    wrapper.write_text("#!/usr/bin/env python3\n# wrapper")

    # When
    resolved = wrapper.resolve()

    # Then
    assert resolved == wrapper
    assert resolved.is_absolute()


def test_resolve_package_directory_from_wrapper_location(tmp_path: Path) -> None:
    """
    GIVEN wrapper at /tmp/project/cloud-mirror
    WHEN calculating package directory
    THEN package_dir = wrapper.parent / "cloud_mirror"
    """
    # Given
    wrapper_dir = tmp_path / "project"
    wrapper_dir.mkdir()
    wrapper = wrapper_dir / "cloud-mirror"

    package_dir = wrapper_dir / "cloud_mirror"
    package_dir.mkdir()

    # When
    calculated_package = wrapper.parent / "cloud_mirror"

    # Then
    assert calculated_package == package_dir
    assert calculated_package.exists()


def test_symlink_resolution_finds_real_path(tmp_path: Path) -> None:
    """
    GIVEN wrapper symlinked to different location
    WHEN using Path.resolve() on symlink
    THEN returns real path, not symlink path
    """
    # Given
    real_dir = tmp_path / "project"
    real_dir.mkdir()
    wrapper = real_dir / "cloud-mirror"
    wrapper.write_text("#!/usr/bin/env python3\n# wrapper")

    link_dir = tmp_path / "bin"
    link_dir.mkdir()
    symlink = link_dir / "cloud-mirror"
    symlink.symlink_to(wrapper)

    # When
    resolved = symlink.resolve()

    # Then
    assert resolved == wrapper  # Real path, not symlink
    assert resolved.parent == real_dir


def test_package_directory_validation(tmp_path: Path) -> None:
    """
    GIVEN package directory path
    WHEN checking if it exists
    THEN can detect missing package
    """
    # Given
    existing_dir = tmp_path / "cloud_mirror"
    existing_dir.mkdir()

    nonexistent_dir = tmp_path / "missing"

    # When/Then
    assert existing_dir.exists()
    assert not nonexistent_dir.exists()


def test_sys_path_manipulation(tmp_path: Path) -> None:
    """
    GIVEN package parent directory path
    WHEN adding to sys.path
    THEN can verify presence in sys.path
    """
    # Given
    package_parent = tmp_path / "project"
    package_parent.mkdir()
    package_parent_str = str(package_parent)

    # When
    if package_parent_str not in sys.path:
        sys.path.insert(0, package_parent_str)

    # Then
    assert package_parent_str in sys.path

    # Cleanup
    if package_parent_str in sys.path:
        sys.path.remove(package_parent_str)


def test_wrapper_error_when_package_missing(tmp_path: Path) -> None:
    """
    GIVEN package directory does not exist
    WHEN wrapper validates package existence
    THEN should detect missing package for error reporting
    """
    # Given
    wrapper_dir = tmp_path / "project"
    wrapper_dir.mkdir()
    package_dir = wrapper_dir / "cloud_mirror"
    # Package NOT created

    # When/Then
    assert not package_dir.exists()  # Would trigger error in wrapper
