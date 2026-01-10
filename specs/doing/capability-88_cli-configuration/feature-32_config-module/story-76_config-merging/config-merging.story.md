# Story: Config Merging

## Functional Requirements

### FR1: Merge config with precedence order (defaults → profile → CLI)

```gherkin
GIVEN defaults section, profile section, and CLI arguments
WHEN merge_config() is called
THEN returns merged config where CLI args override profile, profile overrides defaults
```

#### Files created/modified

1. `cloud_mirror/config.py` [modify]: Add `merge_config()` function
2. `tests/unit/config/test_config_merging.py` [new]: Unit tests for config merging

### FR2: Handle partial profile specifications

```gherkin
GIVEN profile with only source (no destination)
AND CLI argument provides destination
WHEN merge_config() is called
THEN returns config with profile source + CLI destination
```

#### Files created/modified

1. `cloud_mirror/config.py` [modify]: Support partial profile merging

### FR3: CLI arguments always override profile settings

```gherkin
GIVEN profile specifies source AND destination
AND CLI arguments also specify source AND destination
WHEN merge_config() is called
THEN CLI arguments take precedence over profile
```

#### Files created/modified

1. `cloud_mirror/config.py` [modify]: Ensure CLI precedence logic

## Testing Strategy

> Stories require **Level 1** to prove core logic works.
> See `/context/4-testing-standards.md` for level definitions.

### Level Assignment

| Component                | Level | Justification                            |
| ------------------------ | ----- | ---------------------------------------- |
| Config merging logic     | 1     | Pure dict manipulation, no external deps |
| Precedence order         | 1     | Deterministic logic, testable with dicts |
| Partial profile handling | 1     | Dict merging with None checks            |

### When to Escalate

This story stays at Level 1 because:

- Uses simple dict inputs (no file I/O)
- Pure function - given inputs produce deterministic outputs
- Tests verify merge logic with various combinations

If you find yourself needing integration tests, consider:

1. Is this testing config loading with CLI? → That's feature-level integration (FI tests)
2. Is this testing wrapper script? → That's feature-54 (standalone wrapper)

## Unit Tests (Level 1)

```python
# specs/doing/capability-88_cli-configuration/feature-32_config-module/story-76_config-merging/tests/test_config_merging.py
import pytest
from cloud_mirror.config import merge_config


def test_merge_defaults_and_profile():
    """
    GIVEN defaults with transfers=32
    AND profile with remote='dropbox:photos'
    WHEN merge_config() is called
    THEN returns merged config with both settings
    """
    # Given
    defaults = {"transfers": 32, "keep_versions": 3}
    profile = {"remote": "dropbox:photos"}
    cli_args = {}

    # When
    result = merge_config(defaults, profile, cli_args)

    # Then
    assert result["transfers"] == 32
    assert result["keep_versions"] == 3
    assert result["remote"] == "dropbox:photos"


def test_profile_overrides_defaults():
    """
    GIVEN defaults with transfers=32
    AND profile with transfers=64
    WHEN merge_config() is called
    THEN profile value takes precedence
    """
    # Given
    defaults = {"transfers": 32}
    profile = {"transfers": 64}
    cli_args = {}

    # When
    result = merge_config(defaults, profile, cli_args)

    # Then
    assert result["transfers"] == 64


def test_cli_overrides_profile():
    """
    GIVEN profile with remote='dropbox:photos'
    AND CLI args with remote='b2:backup'
    WHEN merge_config() is called
    THEN CLI value takes precedence
    """
    # Given
    defaults = {}
    profile = {"remote": "dropbox:photos"}
    cli_args = {"remote": "b2:backup"}

    # When
    result = merge_config(defaults, profile, cli_args)

    # Then
    assert result["remote"] == "b2:backup"


def test_cli_overrides_both_defaults_and_profile():
    """
    GIVEN defaults with transfers=32
    AND profile with transfers=64
    AND CLI args with transfers=128
    WHEN merge_config() is called
    THEN CLI value takes precedence over both
    """
    # Given
    defaults = {"transfers": 32}
    profile = {"transfers": 64}
    cli_args = {"transfers": 128}

    # When
    result = merge_config(defaults, profile, cli_args)

    # Then
    assert result["transfers"] == 128


def test_partial_profile_with_source_only():
    """
    GIVEN profile with source='tank/photos' (no destination)
    AND CLI args with destination='dropbox:backup'
    WHEN merge_config() is called
    THEN returns config with both source and destination
    """
    # Given
    defaults = {}
    profile = {"source": "tank/photos", "transfers": 64}
    cli_args = {"destination": "dropbox:backup"}

    # When
    result = merge_config(defaults, profile, cli_args)

    # Then
    assert result["source"] == "tank/photos"
    assert result["destination"] == "dropbox:backup"
    assert result["transfers"] == 64


def test_partial_profile_with_destination_only():
    """
    GIVEN profile with destination='dropbox:photos' (no source)
    AND CLI args with source='tank/photos'
    WHEN merge_config() is called
    THEN returns config with both source and destination
    """
    # Given
    defaults = {}
    profile = {"destination": "dropbox:photos", "keep_versions": 5}
    cli_args = {"source": "tank/photos"}

    # When
    result = merge_config(defaults, profile, cli_args)

    # Then
    assert result["source"] == "tank/photos"
    assert result["destination"] == "dropbox:photos"
    assert result["keep_versions"] == 5


def test_empty_inputs_returns_empty_config():
    """
    GIVEN all empty dicts
    WHEN merge_config() is called
    THEN returns empty config
    """
    # Given
    defaults = {}
    profile = {}
    cli_args = {}

    # When
    result = merge_config(defaults, profile, cli_args)

    # Then
    assert result == {}


def test_none_profile_handled_gracefully():
    """
    GIVEN defaults and CLI args, but None for profile
    WHEN merge_config() is called
    THEN merges defaults and CLI without error
    """
    # Given
    defaults = {"transfers": 32}
    profile = None
    cli_args = {"remote": "dropbox:backup"}

    # When
    result = merge_config(defaults, profile, cli_args)

    # Then
    assert result["transfers"] == 32
    assert result["remote"] == "dropbox:backup"
```

## Architectural Requirements

### Relevant ADRs

1. `specs/doing/capability-88_cli-configuration/decisions/adr-001_toml-config-with-profiles.md` - Merge precedence order, profile handling

## Quality Requirements

### QR1: Type Safety

**Requirement:** All functions must have Python type annotations
**Target:** 100% type coverage
**Validation:** `uv run --extra dev mypy cloud_mirror/config.py` passes

### QR2: Precedence Correctness

**Requirement:** Merge order must be strictly enforced: defaults → profile → CLI
**Target:** CLI args always win, profile overrides defaults
**Validation:** Unit tests verify all precedence combinations

### QR3: Graceful None Handling

**Requirement:** Handle None profile gracefully (when no profile specified)
**Target:** merge_config() works with profile=None
**Validation:** Unit test verifies None profile doesn't crash

## Completion Criteria

- [ ] All Level 1 unit tests pass (8+ tests covering all precedence cases)
- [ ] No mocking (uses dict inputs)
- [ ] BDD structure (GIVEN/WHEN/THEN) in all tests
- [ ] Type annotations on all functions
- [ ] Handles None profile without error
- [ ] Merge order strictly enforced: defaults < profile < CLI

## Documentation

1. Docstring on `merge_config()` documenting precedence order and use cases
