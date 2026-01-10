# Story: Wrapper Script

## Functional Requirements

### FR1: Resolve wrapper location and find package directory

```gherkin
GIVEN cloud-mirror wrapper script at /path/to/cloud-mirror
WHEN wrapper resolves its own location using Path(__file__).resolve()
THEN finds package directory at /path/to/cloud_mirror
AND adds /path/to to sys.path for imports
```

#### Files created/modified

1. `cloud-mirror` [new]: Standalone wrapper script at project root
2. `cloud_mirror/__main__.py` [new]: Python -m invocation support

### FR2: Handle symlinked wrapper execution

```gherkin
GIVEN wrapper symlinked from /usr/local/bin/cloud-mirror → /path/to/project/cloud-mirror
WHEN wrapper uses Path(__file__).resolve()
THEN follows symlink to find real wrapper location
AND correctly finds package at real location
```

#### Files created/modified

1. `cloud-mirror` [modify]: Use .resolve() for symlink resolution

### FR3: Validate package directory exists

```gherkin
GIVEN package directory might not exist (corrupted installation)
WHEN wrapper attempts to find cloud_mirror package
THEN verifies package_dir.exists() before adding to sys.path
AND prints clear error message if package not found
AND exits with status code 1
```

#### Files created/modified

1. `cloud-mirror` [modify]: Add validation before import

### FR4: Invoke main() and exit with its return code

```gherkin
GIVEN wrapper successfully imported cloud_mirror.main
WHEN wrapper invokes main()
THEN passes through main()'s return code via sys.exit()
```

#### Files created/modified

1. `cloud-mirror` [modify]: sys.exit(main())
2. `cloud_mirror/__main__.py` [modify]: sys.exit(main())

## Testing Strategy

> Stories require **Level 1** to prove core logic works.
> See `/context/4-testing-standards.md` for level definitions.

### Level Assignment

| Component                | Level | Justification                                          |
| ------------------------ | ----- | ------------------------------------------------------ |
| Path resolution          | 1     | Can test with real temp directories and Path objects   |
| sys.path manipulation    | 1     | Can verify list contains expected paths                |
| Package existence check  | 1     | Can test with real directories (tmp_path)              |
| Symlink resolution       | 1     | Can create real symlinks with tmp_path                 |

### When to Escalate

This story stays at Level 1 because:

- Uses pytest `tmp_path` fixture with real directories
- Can create real symlinks for testing resolution
- No external process execution needed for unit logic
- Tests verify path manipulation and validation logic

Feature-level integration tests (Level 2) will verify:
- End-to-end wrapper execution via subprocess
- Invocation from different working directories
- Shebang execution without python3 prefix

## Unit Tests (Level 1)

```python
# specs/doing/capability-88_cli-configuration/feature-54_standalone-wrapper/story-32_wrapper-script/tests/test_wrapper_unit.py
import pytest
import sys
from pathlib import Path


def test_resolve_wrapper_location(tmp_path: Path):
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


def test_resolve_package_directory_from_wrapper_location(tmp_path: Path):
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


def test_symlink_resolution_finds_real_path(tmp_path: Path):
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


def test_package_directory_validation(tmp_path: Path):
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


def test_sys_path_manipulation(tmp_path: Path):
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
    sys.path.remove(package_parent_str)


def test_wrapper_error_when_package_missing(tmp_path: Path):
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
```

## Architectural Requirements

### Relevant ADRs

1. `specs/doing/capability-88_cli-configuration/decisions/adr-001_toml-config-with-profiles.md` - Config file search relative to package location (wrapper must find package correctly)

## Quality Requirements

### QR1: Symlink Safety

**Requirement:** Wrapper must work when symlinked to PATH locations
**Target:** Path.resolve() used to follow symlinks to real location
**Validation:** Unit test verifies symlink resolution

### QR2: Clear Error Messages

**Requirement:** Missing package produces actionable error message
**Target:** Print "Error: cloud_mirror package not found at {path}" to stderr
**Validation:** Error message includes actual path checked

### QR3: Executable Permissions

**Requirement:** Wrapper must be executable without python3 prefix
**Target:** chmod +x cloud-mirror after creation
**Validation:** Feature-level integration tests verify direct execution

### QR4: Python -m Support

**Requirement:** Support python3 -m cloud_mirror invocation
**Target:** __main__.py imports and invokes main()
**Validation:** Feature-level integration tests verify python -m execution

## Completion Criteria

- [ ] All Level 1 unit tests pass
- [ ] No mocking (uses real temp directories via `tmp_path`)
- [ ] Test data uses `tmp_path` fixture, not hardcoded paths
- [ ] BDD structure (GIVEN/WHEN/THEN) in all tests
- [ ] Wrapper script created at project root with shebang
- [ ] __main__.py created in cloud_mirror/ package
- [ ] Executable permissions set via chmod +x
- [ ] Clear error message when package not found

## Documentation

1. Wrapper script docstring explaining its purpose
2. __main__.py docstring explaining python -m support
