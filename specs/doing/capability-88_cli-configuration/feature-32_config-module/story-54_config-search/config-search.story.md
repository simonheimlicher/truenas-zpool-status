# Story: Config Search

## Functional Requirements

### FR1: Find config file relative to package location

```gherkin
GIVEN cloud-mirror.toml exists in package parent directory
WHEN find_config_file() is called with package directory path
THEN returns Path to the config file
```

#### Files created/modified

1. `cloud_mirror/config.py` [modify]: Add `find_config_file()` function
2. `tests/unit/config/test_config_search.py` [new]: Unit tests for config search

### FR2: Return None when config file not found

```gherkin
GIVEN no cloud-mirror.toml exists in search paths
WHEN find_config_file() is called
THEN returns None (graceful fallback, no exception)
```

#### Files created/modified

1. `cloud_mirror/config.py` [modify]: Handle missing config gracefully

### FR3: Search multiple locations in order

```gherkin
GIVEN multiple possible config locations
WHEN find_config_file() is called
THEN searches in order: package_dir/cloud-mirror.toml, package_dir.parent/cloud-mirror.toml
AND returns first config file found
```

#### Files created/modified

1. `cloud_mirror/config.py` [modify]: Implement search order logic

## Testing Strategy

> Stories require **Level 1** to prove core logic works.
> See `/context/4-testing-standards.md` for level definitions.

### Level Assignment

| Component               | Level | Justification                                       |
| ----------------------- | ----- | --------------------------------------------------- |
| Config file search      | 1     | Path.exists() checks with real temp directories     |
| Search order logic      | 1     | Deterministic path checking, testable with tmp_path |
| Missing config handling | 1     | Pure logic, no external dependencies                |

### When to Escalate

This story stays at Level 1 because:

- Uses pytest `tmp_path` fixture with real directories and files
- No mocking needed - real filesystem operations via Path objects
- Tests verify search order with actual file creation

If you find yourself needing integration tests, consider:

1. Is this testing symlink resolution? → That's feature-level integration (covered by FI tests)
2. Is this testing profile merging? → That's story-76 (config merging)

## Unit Tests (Level 1)

```python
# specs/doing/capability-88_cli-configuration/feature-32_config-module/story-54_config-search/tests/test_config_search.py
import pytest
from pathlib import Path
from cloud_mirror.config import find_config_file


def test_find_config_in_parent_directory(tmp_path: Path):
    """
    GIVEN cloud-mirror.toml in parent directory
    WHEN find_config_file() is called with package directory
    THEN returns Path to config file in parent
    """
    # Given
    package_dir = tmp_path / "cloud_mirror"
    package_dir.mkdir()
    config_file = tmp_path / "cloud-mirror.toml"
    config_file.write_text("[defaults]\ntransfers = 64\n")

    # When
    result = find_config_file(package_dir)

    # Then
    assert result == config_file
    assert result.exists()


def test_find_config_in_package_directory(tmp_path: Path):
    """
    GIVEN cloud-mirror.toml in package directory itself
    WHEN find_config_file() is called
    THEN returns Path to config file in package directory
    """
    # Given
    package_dir = tmp_path / "cloud_mirror"
    package_dir.mkdir()
    config_file = package_dir / "cloud-mirror.toml"
    config_file.write_text("[defaults]\ntransfers = 64\n")

    # When
    result = find_config_file(package_dir)

    # Then
    assert result == config_file
    assert result.exists()


def test_search_order_prefers_package_dir_over_parent(tmp_path: Path):
    """
    GIVEN cloud-mirror.toml exists in BOTH package directory AND parent
    WHEN find_config_file() is called
    THEN returns config from package directory (higher precedence)
    """
    # Given
    package_dir = tmp_path / "cloud_mirror"
    package_dir.mkdir()

    # Config in both locations (different content to verify which is returned)
    parent_config = tmp_path / "cloud-mirror.toml"
    parent_config.write_text("[defaults]\ntransfers = 32\n")

    package_config = package_dir / "cloud-mirror.toml"
    package_config.write_text("[defaults]\ntransfers = 64\n")

    # When
    result = find_config_file(package_dir)

    # Then
    assert result == package_config
    assert "transfers = 64" in result.read_text()


def test_returns_none_when_config_not_found(tmp_path: Path):
    """
    GIVEN no cloud-mirror.toml in any search location
    WHEN find_config_file() is called
    THEN returns None (graceful fallback)
    """
    # Given
    package_dir = tmp_path / "cloud_mirror"
    package_dir.mkdir()
    # No config file created

    # When
    result = find_config_file(package_dir)

    # Then
    assert result is None


def test_handles_nonexistent_package_directory(tmp_path: Path):
    """
    GIVEN package directory does not exist
    WHEN find_config_file() is called
    THEN returns None without raising exception
    """
    # Given
    nonexistent_dir = tmp_path / "nonexistent"
    # Directory NOT created

    # When
    result = find_config_file(nonexistent_dir)

    # Then
    assert result is None
```

## Architectural Requirements

### Relevant ADRs

1. `specs/doing/capability-88_cli-configuration/decisions/adr-001_toml-config-with-profiles.md` - Config file location, search order

## Quality Requirements

### QR1: Type Safety

**Requirement:** All functions must have Python type annotations
**Target:** 100% type coverage
**Validation:** `uv run --extra dev mypy cloud_mirror/config.py` passes

### QR2: Graceful Degradation

**Requirement:** Missing config must not crash (return None for graceful fallback)
**Target:** find_config_file() returns None when config not found
**Validation:** Unit tests verify None return value

### QR3: Search Order Determinism

**Requirement:** Config search must be deterministic and documented
**Target:** Always search package_dir first, then parent
**Validation:** Unit test verifies precedence when config in both locations

## Completion Criteria

- [ ] All Level 1 unit tests pass
- [ ] No mocking (uses real temp directories via `tmp_path`)
- [ ] Test data uses `tmp_path` fixture, not hardcoded paths
- [ ] BDD structure (GIVEN/WHEN/THEN) in all tests
- [ ] Type annotations on all functions
- [ ] find_config_file() returns None when config not found (not exception)

## Documentation

1. Docstring on `find_config_file()` documenting search order
