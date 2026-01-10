# Feature: Config Module

## Observable Outcome

A `cloud_mirror/config.py` module that searches for TOML config files relative to the package location, parses them with stdlib `tomllib`, and merges settings from defaults, profiles, and CLI args with correct precedence.

## Testing Strategy

> Features require **Level 1 + Level 2** to prove the feature works with real tools.
> See `/context/4-testing-standards.md` for level definitions.

### Level Assignment

| Component              | Level | Justification                                            |
| ---------------------- | ----- | -------------------------------------------------------- |
| TOML parsing           | 1     | Pure function, can test with tempfile TOML content       |
| Config search logic    | 1     | Pure function, can test with mocked Path.exists()        |
| Config merging         | 1     | Pure function, can test with dict inputs                 |
| Real filesystem search | 2     | Needs real directory structure to verify path resolution |
| Symlink resolution     | 2     | Needs actual symlinks to verify Path.resolve() behavior  |

### Escalation Rationale

- **1 → 2**: Unit tests prove our search, parse, and merge logic works in isolation. Level 2 verifies that the module correctly finds TOML files in real directory structures, including when the calling script is symlinked from another location. This catches edge cases like relative path resolution and symlink following that mocks cannot simulate.

## Feature Integration Tests (Level 2)

These tests verify that **real filesystem and TOML parsing** work together as expected.

###FI1: Config file found relative to package location

```python
# specs/doing/capability-88_cli-configuration/feature-32_config-module/tests/test_config_integration.py
import tempfile
from pathlib import Path
import pytest


def test_config_found_relative_to_package():
    """
    GIVEN cloud_mirror package with cloud-mirror.toml in same directory
    WHEN load_config() is called from that package
    THEN TOML config is found and loaded correctly
    """
    # Given: Package directory with TOML config
    with tempfile.TemporaryDirectory() as tmpdir:
        package_dir = Path(tmpdir) / "cloud_mirror"
        package_dir.mkdir()

        config_file = package_dir.parent / "cloud-mirror.toml"
        config_file.write_text("""
[defaults]
transfers = 32
keep_versions = 3

[profiles.test]
remote = "dropbox:test"
""")

        # Simulate calling from within package
        # When: Load config (with package_dir as context)
        from cloud_mirror.config import load_config

        config = load_config(package_dir=package_dir)

        # Then: Config loaded with defaults
        assert config["transfers"] == 32
        assert config["keep_versions"] == 3
        assert "test" in config["profiles"]
        assert config["profiles"]["test"]["remote"] == "dropbox:test"
```

### FI2: Config search fallback when TOML missing

```python
def test_config_fallback_when_toml_missing():
    """
    GIVEN package directory with NO cloud-mirror.toml
    WHEN load_config() is called
    THEN returns default config without error
    """
    # Given: Package directory without TOML
    with tempfile.TemporaryDirectory() as tmpdir:
        package_dir = Path(tmpdir) / "cloud_mirror"
        package_dir.mkdir()

        # When: Load config
        from cloud_mirror.config import load_config

        config = load_config(package_dir=package_dir)

        # Then: Default config returned (no crash)
        assert isinstance(config, dict)
        assert config.get("profiles", {}) == {}
```

### FI3: Malformed TOML produces clear error

```python
def test_malformed_toml_error_message():
    """
    GIVEN cloud-mirror.toml with syntax error
    WHEN load_config() is called
    THEN raises exception with clear error message
    """
    # Given: Invalid TOML
    with tempfile.TemporaryDirectory() as tmpdir:
        package_dir = Path(tmpdir) / "cloud_mirror"
        package_dir.mkdir()

        config_file = package_dir.parent / "cloud-mirror.toml"
        config_file.write_text("""
[defaults
missing_closing_bracket = true
""")

        # When/Then: Load raises exception with line number
        from cloud_mirror.config import load_config, ConfigError

        with pytest.raises(ConfigError, match=r"line \d+"):
            load_config(package_dir=package_dir)
```

## Capability Contribution

This feature provides the foundation for capability-88 (CLI Configuration Management). It enables:

- Auto-detection of config files without explicit `--config` flags
- Profile support (loaded by feature-76)
- Separation of concerns: config logic isolated from CLI parsing

Integration points:

- Used by feature-76 (Profile Integration) to load profile settings
- Config search results passed to existing `cloud_mirror.cli` and `cloud_mirror.main`

## Completion Criteria

- [ ] All Level 1 tests pass (unit tests for parse, search, merge)
- [ ] All Level 2 integration tests pass (real filesystem + TOML)
- [ ] `cloud_mirror/config.py` module created and tested
- [ ] Escalation rationale documented

**Note**: To see current stories in this feature, use `ls` or `find` to list story directories (e.g., `story-*`) within the feature's directory.
