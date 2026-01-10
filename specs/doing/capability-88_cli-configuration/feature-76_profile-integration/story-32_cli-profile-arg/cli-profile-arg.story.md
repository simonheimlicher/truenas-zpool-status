# Story: CLI Profile Argument

## Functional Requirements

### FR1: Add --profile flag to argument parser

```gherkin
GIVEN cloud-mirror CLI argument parser
WHEN --profile NAME flag is added
THEN parser accepts --profile as optional argument
AND stores profile name in parsed namespace
```

#### Files created/modified

1. `cloud_mirror/cli.py` [modify]: Add --profile argument to parser

### FR2: Make source/destination positional arguments optional

```gherkin
GIVEN source and destination are currently required positional arguments
WHEN --profile flag is used without positionals
THEN parser allows source/destination to be None
AND validation happens later in main() after config merging
```

#### Files created/modified

1. `cloud_mirror/cli.py` [modify]: Change nargs="?" for source/destination

### FR3: Support mixed usage (profile + positionals)

```gherkin
GIVEN --profile flag and positional arguments
WHEN both are provided: cloud-mirror testpool/data --profile backup
THEN parser accepts both
AND CLI args will override profile settings (validated in main())
```

#### Files created/modified

1. `cloud_mirror/cli.py` [modify]: No conflicts between --profile and positionals

## Testing Strategy

> Stories require **Level 1** to prove core logic works.
> See `/context/4-testing-standards.md` for level definitions.

### Level Assignment

| Component                           | Level | Justification                              |
| ----------------------------------- | ----- | ------------------------------------------ |
| Argument parser with --profile      | 1     | Pure argparse logic, testable with strings |
| Optional positional args            | 1     | argparse nargs="?" testable directly       |
| Mixed usage (profile + positionals) | 1     | Parser acceptance logic, no I/O needed     |

### When to Escalate

This story stays at Level 1 because:

- Tests only verify argparse configuration
- No file I/O or external dependencies
- Uses parse_args() directly with test argv lists
- Validation logic tested separately in story-54

Feature-level integration tests (Level 2) will verify:

- End-to-end profile loading and merging
- CLI precedence over profile values
- Error messages for missing profiles

## Unit Tests (Level 1)

```python
# specs/doing/capability-88_cli-configuration/feature-76_profile-integration/story-32_cli-profile-arg/tests/test_cli_profile_arg.py
import pytest
from cloud_mirror.cli import parse_args


def test_parse_args_with_profile_flag():
    """
    GIVEN cloud-mirror CLI with --profile flag
    WHEN parsing args: ["--profile", "photos"]
    THEN parsed.profile == "photos"
    """
    # When
    args = parse_args(["--profile", "photos", "src", "dest"])

    # Then
    assert args.profile == "photos"
    assert args.source == "src"
    assert args.destination == "dest"


def test_parse_args_profile_with_optional_positionals():
    """
    GIVEN --profile flag without positional arguments
    WHEN parsing args: ["--profile", "backup"]
    THEN parsed.profile == "backup"
    AND parsed.source is None
    AND parsed.destination is None
    """
    # When
    args = parse_args(["--profile", "backup"])

    # Then
    assert args.profile == "backup"
    assert args.source is None
    assert args.destination is None


def test_parse_args_positionals_without_profile():
    """
    GIVEN positional args without --profile
    WHEN parsing args: ["testpool/data", "dropbox:backup"]
    THEN positionals parsed normally
    AND parsed.profile is None
    """
    # When
    args = parse_args(["testpool/data", "dropbox:backup"])

    # Then
    assert args.source == "testpool/data"
    assert args.destination == "dropbox:backup"
    assert args.profile is None


def test_parse_args_partial_positionals_with_profile():
    """
    GIVEN --profile with only source positional
    WHEN parsing args: ["testpool/photos", "--profile", "backup"]
    THEN source from positional, destination from profile (merged in main)
    """
    # When
    args = parse_args(["testpool/photos", "--profile", "backup"])

    # Then
    assert args.source == "testpool/photos"
    assert args.destination is None  # Will be filled from profile in main()
    assert args.profile == "backup"
```

## Architectural Requirements

### Relevant ADRs

1. `specs/doing/capability-88_cli-configuration/decisions/adr-001_toml-config-with-profiles.md` - Profile-based configuration
2. Feature 32 (Config Module) provides load_config() and merge_config()

## Quality Requirements

### QR1: Backward Compatibility

**Requirement:** Existing invocations must work unchanged
**Target:** `cloud-mirror source dest` works as before (no --profile)
**Validation:** Unit test verifies positionals-only invocation

### QR2: Type Safety

**Requirement:** Profile argument properly typed
**Target:** --profile accepts string, defaults to None
**Validation:** `uv run --extra dev mypy cloud_mirror/cli.py` passes

### QR3: Help Text Clarity

**Requirement:** --profile flag has clear help text
**Target:** Help mentions loading settings from cloud-mirror.toml
**Validation:** Manual inspection of --help output

## Completion Criteria

- [ ] All Level 1 unit tests pass
- [ ] No external dependencies (pure argparse testing)
- [ ] BDD structure (GIVEN/WHEN/THEN) in all tests
- [ ] --profile flag added to parser
- [ ] source/destination made optional (nargs="?")
- [ ] Backward compatibility preserved (positionals-only works)
- [ ] Type annotations correct

## Documentation

1. Update --profile help text in parser
2. Note in story DONE.md: validation happens in main(), not parser
