# Story: TOML Parsing

## Functional Requirements

### FR1: Parse TOML config with defaults and profiles

```gherkin
GIVEN a cloud-mirror.toml file with [defaults] and [profiles.*] sections
WHEN parse_toml() is called with the file path
THEN returns dict with 'defaults' and 'profiles' keys containing parsed sections
```

#### Files created/modified

1. `cloud_mirror/config.py` [new]: TOML parsing functions
2. `tests/unit/config/test_toml_parsing.py` [new]: Unit tests for TOML parsing

### FR2: Handle malformed TOML with clear error

```gherkin
GIVEN a TOML file with syntax errors
WHEN parse_toml() is called
THEN raises ConfigError with line number in error message
```

#### Files created/modified

1. `cloud_mirror/config.py` [modify]: Add ConfigError exception class

## Testing Strategy

> Stories require **Level 1** to prove core logic works.
> See `/context/4-testing-standards.md` for level definitions.

### Level Assignment

| Component          | Level | Justification                               |
| ------------------ | ----- | ------------------------------------------- |
| TOML parsing       | 1     | Pure function using stdlib tomllib          |
| Error handling     | 1     | Exception wrapping, no external deps        |
| Section extraction | 1     | Dict manipulation, no external dependencies |

### When to Escalate

This story stays at Level 1 because:

- We're testing `tomllib.load()` behavior with real files, not external services
- Uses pytest `tmp_path` fixture with real TOML files (per ADR)
- No mocking needed - stdlib TOML parser is the real implementation

If you find yourself needing integration tests, consider:

1. Is this testing file system integration? → That's story-54 (config search)
2. Is this testing profile merging? → That's story-76 (config merging)

## Unit Tests (Level 1)

```python
# tests/unit/config/test_toml_parsing.py
import pytest
from pathlib import Path
from cloud_mirror.config import parse_toml, ConfigError


def test_parse_toml_with_defaults_and_profiles(tmp_path: Path):
    """
    GIVEN cloud-mirror.toml with [defaults] and [profiles.photos]
    WHEN parse_toml() is called
    THEN returns dict with both sections
    """
    # Given
    config_file = tmp_path / "cloud-mirror.toml"
    config_file.write_text("""
[defaults]
transfers = 64
keep_versions = 3

[profiles.photos]
remote = "dropbox:photos"
""")

    # When
    config = parse_toml(config_file)

    # Then
    assert config["defaults"]["transfers"] == 64
    assert config["profiles"]["photos"]["remote"] == "dropbox:photos"


def test_parse_toml_malformed_raises_config_error(tmp_path: Path):
    """
    GIVEN TOML with syntax error
    WHEN parse_toml() is called
    THEN raises ConfigError with line number
    """
    # Given
    config_file = tmp_path / "bad.toml"
    config_file.write_text("""
[defaults
missing_bracket = true
""")

    # When/Then
    with pytest.raises(ConfigError, match=r"line \d+"):
        parse_toml(config_file)
```

## Architectural Requirements

### Relevant ADRs

1. `specs/doing/capability-88_cli-configuration/decisions/adr-001_toml-config-with-profiles.md` - TOML format, parsing requirements

## Quality Requirements

### QR1: Type Safety

**Requirement:** All functions must have Python type annotations
**Target:** 100% type coverage
**Validation:** `uv run --extra dev mypy cloud_mirror/config.py` passes

### QR2: Error Handling

**Requirement:** Malformed TOML must produce clear error messages with line numbers
**Target:** ConfigError wraps tomllib.TOMLDecodeError with actionable message
**Validation:** Unit tests verify error messages contain line numbers

### QR3: Stdlib Only

**Requirement:** Use Python 3.11 stdlib `tomllib` only (no external TOML libraries)
**Target:** No imports of `toml`, `tomlkit`, or other external parsers
**Validation:** `ruff check` enforces no banned imports

## Completion Criteria

- [ ] All Level 1 unit tests pass
- [ ] No mocking (uses real temp files via `tmp_path`)
- [ ] Test data uses `tmp_path` fixture, not hardcoded paths
- [ ] BDD structure (GIVEN/WHEN/THEN) in all tests
- [ ] Type annotations on all functions
- [ ] ConfigError provides line numbers for syntax errors

## Documentation

1. Docstrings on `parse_toml()` and `ConfigError`
