# Capability: CLI Configuration Management

## Success Metric

**Quantitative Target:**

- **Baseline**: Every cloud-mirror invocation requires `python3 -m cloud_mirror` and `--config <path>` flag (verbose)
- **Target**: Standalone `cloud-mirror` command with auto-detected config and optional profiles
- **Measurement**: Cron job command length (from ~120 chars to ~50 chars for common cases)

## Testing Strategy

> Capabilities require **all three levels** to prove end-to-end value delivery.
> See `/context/4-testing-standards.md` for level definitions.

### Level Assignment

| Component            | Level | Justification                                         |
| -------------------- | ----- | ----------------------------------------------------- |
| Config path search   | 1     | Unit tests verify search logic without filesystem     |
| TOML parsing/merging | 1     | Unit tests verify config merging with mocked files    |
| Standalone wrapper   | 2     | Integration tests verify wrapper finds package/config |
| Profile application  | 2     | Integration tests verify end-to-end config resolution |
| Cron job invocation  | 3     | E2E test verifies production deployment scenario      |

### Escalation Rationale

- **1 → 2**: Level 1 cannot verify the wrapper script correctly locates the package when symlinked or invoked from different directories. Level 2 confirms real filesystem behavior.
- **2 → 3**: Level 2 cannot verify the solution works on TrueNAS SCALE with only Python 3.11 stdlib. Level 3 confirms zero external dependencies and PATH installation works.

## Capability E2E Tests (Level 3)

These tests verify the **complete user journey** delivers value.

### E2E1: Standalone wrapper with profile (simulates cron job)

```python
# specs/doing/capability-88_cli-configuration/tests/test_cli_configuration_e2e.py
import subprocess
import tempfile
from pathlib import Path
import pytest


def test_standalone_wrapper_with_profile():
    """
    GIVEN cloud-mirror installed with TOML config and wrapper symlinked to PATH
    WHEN invoked via standalone wrapper with --profile flag
    THEN auto-detects config, applies profile settings, runs without errors
    """
    # Given: Simulated installation
    with tempfile.TemporaryDirectory() as tmpdir:
        install_dir = Path(tmpdir) / "cloud-mirror"
        install_dir.mkdir()

        # Create TOML config
        config = install_dir / "cloud-mirror.toml"
        config.write_text("""
[defaults]
transfers = 32

[profiles.test]
remote = "mockremote:backup"
keep_versions = 2
""")

        # Create rclone config
        rclone_conf = install_dir / "rclone.conf"
        rclone_conf.write_text("[mockremote]\ntype = local\n")

        # Symlink wrapper to temporary bin
        bin_dir = Path(tmpdir) / "bin"
        bin_dir.mkdir()
        wrapper_link = bin_dir / "cloud-mirror"
        wrapper_link.symlink_to(Path.cwd() / "cloud-mirror")

        # When: Invoke via symlink with profile
        env = {"PATH": f"{bin_dir}:{os.environ['PATH']}"}
        result = subprocess.run(
            ["cloud-mirror", "testpool/data", "--profile", "test", "--dry-run", "-v"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            env=env,
        )

        # Then: Success with profile applied
        assert result.returncode == 0
        assert "mockremote:backup" in result.stdout
        assert "transfers=32" in result.stdout
        assert "keep_versions=2" in result.stdout
```

### E2E2: Auto-detect config without explicit flag

```python
def test_autodetect_config_from_package_location():
    """
    GIVEN cloud-mirror installed with rclone.conf in same directory
    WHEN invoked without --config flag
    THEN auto-detects rclone.conf relative to package location
    """
    # Given: Config in package directory
    with tempfile.TemporaryDirectory() as tmpdir:
        install_dir = Path(tmpdir) / "cloud-mirror"
        install_dir.mkdir()

        rclone_conf = install_dir / "rclone.conf"
        rclone_conf.write_text("[mockremote]\ntype = local\n")

        # When: Invoke without --config
        result = subprocess.run(
            [
                "python3",
                "-m",
                "cloud_mirror",
                "testpool/data",
                "mockremote:backup",
                "--dry-run",
                "-v",
            ],
            cwd=install_dir,
            capture_output=True,
            text=True,
            env={"PYTHONPATH": str(install_dir.parent)},
        )

        # Then: Config auto-detected
        assert result.returncode == 0
        assert str(rclone_conf) in result.stdout or "rclone.conf" in result.stdout
```

## System Integration

This capability enhances the CLI layer without modifying core functionality:

- **Integrates with**: `cloud_mirror.cli` (argument parsing), `cloud_mirror.main` (entry point)
- **Used by**: All invocations (push, pull, sync)
- **Dependencies**: None (Python 3.11 stdlib only)
- **Coordination**: Must work with existing `--config` flag (CLI takes precedence)

## Completion Criteria

- [ ] All Level 1 tests pass (unit tests for config search, TOML parsing, merging)
- [ ] All Level 2 tests pass (integration tests for wrapper, profile application)
- [ ] All Level 3 E2E tests pass (end-to-end cron job scenario)
- [ ] Success metric achieved (cron job command length reduced by >50%)
- [ ] Zero external dependencies (Python 3.11 stdlib only)

**Note**: To see current features in this capability, use `ls` or `find` to list feature directories (e.g., `feature-*`) within this capability's folder.
