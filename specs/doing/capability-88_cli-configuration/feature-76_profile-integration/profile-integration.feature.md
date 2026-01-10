# Feature: Profile Integration

## Observable Outcome

The CLI accepts a `--profile NAME` flag that loads settings from `cloud-mirror.toml`, merges them with defaults and CLI args (CLI takes precedence), and allows profiles to specify source, destination, or both for flexible reuse.

## Testing Strategy

> Features require **Level 1 + Level 2** to prove the feature works with real tools.
> See `/context/4-testing-standards.md` for level definitions.

### Level Assignment

| Component                        | Level | Justification                                             |
| -------------------------------- | ----- | --------------------------------------------------------- |
| Profile extraction from TOML     | 1     | Pure function, test with dict inputs                      |
| Config merging precedence        | 1     | Pure function, verify defaults → profile → CLI order      |
| CLI arg parsing with --profile   | 1     | Can test argparse with mock args                          |
| End-to-end profile application   | 2     | Needs real TOML + CLI integration to verify full dataflow |
| Profile with partial source/dest | 2     | Verify mixing profile and CLI positional args works       |

### Escalation Rationale

- **1 → 2**: Unit tests prove that profile extraction, merging logic, and argparse work independently. Level 2 verifies the entire chain: CLI parses `--profile`, config module loads TOML, profile settings merge with CLI args correctly, and the final config passes to direction detection and execution. This catches integration bugs where pieces work alone but fail together (e.g., arg order, type mismatches, missing keys).

## Feature Integration Tests (Level 2)

These tests verify that **profiles work end-to-end** with CLI and config loading.

### FI1: Profile loads and merges with CLI args

```python
# specs/doing/capability-88_cli-configuration/feature-76_profile-integration/tests/test_profile_integration.py
import subprocess
import tempfile
from pathlib import Path


def test_profile_merges_with_cli_args():
    """
    GIVEN cloud-mirror.toml with profile defining remote and keep_versions
    WHEN invoked with --profile and source as CLI arg
    THEN profile settings merge with CLI arg (CLI source overrides)
    """
    # Given: TOML with profile
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "cloud-mirror.toml"
        config_file.write_text("""
[defaults]
transfers = 32

[profiles.photos]
remote = "dropbox-photos:backup"
keep_versions = 5
""")

        # When: Invoke with --profile and CLI source
        result = subprocess.run(
            [
                "python3",
                "-m",
                "cloud_mirror",
                "testpool/photos",  # CLI source
                "--profile",
                "photos",
                "--dry-run",
                "-v",
            ],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            env={"PYTHONPATH": str(tmpdir)},
        )

        # Then: Profile remote used, CLI source used, defaults applied
        assert result.returncode == 0
        assert "dropbox-photos:backup" in result.stdout
        assert "testpool/photos" in result.stdout
        assert "keep_versions=5" in result.stdout or "keep-versions 5" in result.stdout
        assert "transfers=32" in result.stdout or "transfers 32" in result.stdout
```

### FI2: CLI args override profile settings

```python
def test_cli_args_override_profile():
    """
    GIVEN profile with keep_versions = 5
    WHEN invoked with --profile AND --keep-versions 10
    THEN CLI value (10) takes precedence over profile (5)
    """
    # Given: Profile with keep_versions
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "cloud-mirror.toml"
        config_file.write_text("""
[profiles.test]
remote = "dropbox:test"
keep_versions = 5
""")

        # When: CLI overrides keep_versions
        result = subprocess.run(
            [
                "python3",
                "-m",
                "cloud_mirror",
                "testpool/data",
                "--profile",
                "test",
                "--keep-versions",
                "10",
                "--dry-run",
                "-v",
            ],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            env={"PYTHONPATH": str(tmpdir)},
        )

        # Then: CLI value wins
        assert result.returncode == 0
        assert (
            "keep_versions=10" in result.stdout or "keep-versions 10" in result.stdout
        )
```

### FI3: Profile with both source and destination works standalone

```python
def test_profile_with_full_spec():
    """
    GIVEN profile with both source and destination specified
    WHEN invoked with --profile only (no positional args)
    THEN uses profile's source and destination
    """
    # Given: Fully-specified profile
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "cloud-mirror.toml"
        config_file.write_text("""
[profiles.full]
source = "testpool/data"
destination = "dropbox:backup"
keep_versions = 3
""")

        # When: Invoke with profile only
        result = subprocess.run(
            ["python3", "-m", "cloud_mirror", "--profile", "full", "--dry-run", "-v"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            env={"PYTHONPATH": str(tmpdir)},
        )

        # Then: Profile source+dest used
        assert result.returncode == 0
        assert "testpool/data" in result.stdout
        assert "dropbox:backup" in result.stdout
```

### FI4: Missing profile produces clear error

```python
def test_missing_profile_error():
    """
    GIVEN cloud-mirror.toml without 'missing' profile
    WHEN invoked with --profile missing
    THEN produces clear error message
    """
    # Given: TOML without requested profile
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "cloud-mirror.toml"
        config_file.write_text("""
[profiles.exists]
remote = "dropbox:test"
""")

        # When: Request missing profile
        result = subprocess.run(
            [
                "python3",
                "-m",
                "cloud_mirror",
                "testpool/data",
                "--profile",
                "missing",
                "--dry-run",
            ],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            env={"PYTHONPATH": str(tmpdir)},
        )

        # Then: Clear error
        assert result.returncode != 0
        assert "profile" in result.stderr.lower()
        assert "missing" in result.stderr.lower()
```

## Capability Contribution

This feature completes capability-88 (CLI Configuration Management) by enabling profile-based invocation. Users can define common backup tasks in `cloud-mirror.toml` and invoke them with short commands like `cloud-mirror --profile photos`.

Integration points:

- Depends on feature-32 (Config Module) to load TOML and extract profiles
- Works with feature-54 (Standalone Wrapper) for PATH-based invocation
- Extends `cloud_mirror/cli.py` with `--profile` argument
- Passes merged config to existing `cloud_mirror.main` direction detection and execution

## Completion Criteria

- [ ] All Level 1 tests pass (profile extraction, merging, argparse)
- [ ] All Level 2 integration tests pass (end-to-end profile application)
- [ ] `cloud_mirror/cli.py` accepts `--profile` flag
- [ ] Config merging respects precedence: defaults → profile → CLI args
- [ ] Escalation rationale documented

**Note**: To see current stories in this feature, use `ls` or `find` to list story directories (e.g., `story-*`) within the feature's directory.
