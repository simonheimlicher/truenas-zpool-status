"""Integration tests for wrapper script end-to-end execution."""

import os
import stat
import subprocess
from pathlib import Path

import pytest


def test_wrapper_via_symlink(tmp_path: Path) -> None:
    """
    GIVEN wrapper script symlinked to /tmp/bin/cloud-mirror
    WHEN invoked as 'cloud-mirror --help'
    THEN finds package and displays help without errors
    """
    # Given: Symlinked wrapper
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    wrapper_src = Path.cwd() / "cloud-mirror"
    wrapper_link = bin_dir / "cloud-mirror"
    wrapper_link.symlink_to(wrapper_src)

    # When: Invoke via symlink
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    result = subprocess.run(
        [str(wrapper_link), "--help"],
        capture_output=True,
        text=True,
        env=env,
    )

    # Then: Success
    assert result.returncode == 0
    assert "cloud-mirror" in result.stdout.lower()
    assert "Mirror ZFS datasets" in result.stdout


def test_wrapper_from_different_cwd(tmp_path: Path) -> None:
    """
    GIVEN wrapper script in /project/cloud-mirror
    WHEN invoked from /tmp (different cwd)
    THEN still finds package and runs correctly
    """
    # Given: Wrapper at known location
    wrapper = Path.cwd() / "cloud-mirror"
    assert wrapper.exists(), "Wrapper script must exist"

    # When: Invoke from different directory
    result = subprocess.run(
        [str(wrapper), "--help"],
        cwd=str(tmp_path),  # Different working directory
        capture_output=True,
        text=True,
    )

    # Then: Success (package found via wrapper path, not cwd)
    assert result.returncode == 0
    assert "cloud-mirror" in result.stdout.lower()


def test_wrapper_shebang_execution() -> None:
    """
    GIVEN wrapper script with #!/usr/bin/env python3 shebang
    WHEN executed directly (not via python3 wrapper)
    THEN runs successfully
    """
    # Given: Wrapper script
    wrapper = Path.cwd() / "cloud-mirror"

    # Ensure executable bit set
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # When: Execute directly
    result = subprocess.run(
        [str(wrapper), "--help"],
        capture_output=True,
        text=True,
    )

    # Then: Success
    assert result.returncode == 0
    assert "cloud-mirror" in result.stdout.lower()


def test_python_m_invocation() -> None:
    """
    GIVEN cloud_mirror package with __main__.py
    WHEN invoked as 'python3 -m cloud_mirror --help'
    THEN displays help without errors
    """
    # When: Invoke via python -m
    result = subprocess.run(
        ["python3", "-m", "cloud_mirror", "--help"],
        capture_output=True,
        text=True,
    )

    # Then: Success
    assert result.returncode == 0
    assert "cloud-mirror" in result.stdout.lower()
    assert "Mirror ZFS datasets" in result.stdout
