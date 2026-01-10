# Feature: Standalone Wrapper

## Observable Outcome

A `cloud-mirror` executable script at project root that can be symlinked to PATH, resolves its own location to find the `cloud_mirror/` package, and invokes `cloud_mirror.main:main()` without requiring `python3 -m cloud_mirror`.

## Testing Strategy

> Features require **Level 1 + Level 2** to prove the feature works with real tools.
> See `/context/4-testing-standards.md` for level definitions.

### Level Assignment

| Component                  | Level | Justification                                             |
| -------------------------- | ----- | --------------------------------------------------------- |
| Path resolution logic      | 1     | Pure function, can test with mocked Path objects          |
| sys.path manipulation      | 1     | Can verify list manipulation with unit tests              |
| Symlink resolution         | 2     | Needs real symlinks to verify Path.resolve() works        |
| Invocation from other dirs | 2     | Needs real filesystem to test cwd-independent execution   |
| Entry point integration    | 2     | Verifies wrapper correctly invokes cloud_mirror.main:main |

### Escalation Rationale

- **1 → 2**: Unit tests prove path resolution and sys.path logic work in isolation. Level 2 verifies the wrapper actually works when symlinked from `/usr/local/bin/` or other PATH locations, correctly finds the package directory, and successfully imports and invokes the main function. This catches real-world issues with Python import mechanics and symlink traversal that unit tests cannot simulate.

## Feature Integration Tests (Level 2)

These tests verify that **the wrapper works when symlinked** from different locations.

### FI1: Wrapper invoked via symlink finds package

```python
# specs/doing/capability-88_cli-configuration/feature-54_standalone-wrapper/tests/test_wrapper_integration.py
import subprocess
import tempfile
from pathlib import Path


def test_wrapper_via_symlink():
    """
    GIVEN wrapper script symlinked to /tmp/bin/cloud-mirror
    WHEN invoked as 'cloud-mirror --help'
    THEN finds package and displays help without errors
    """
    # Given: Symlinked wrapper
    with tempfile.TemporaryDirectory() as tmpdir:
        bin_dir = Path(tmpdir) / "bin"
        bin_dir.mkdir()

        wrapper_src = Path.cwd() / "cloud-mirror"
        wrapper_link = bin_dir / "cloud-mirror"
        wrapper_link.symlink_to(wrapper_src)

        # When: Invoke via symlink
        env = {"PATH": f"{bin_dir}:{os.environ.get('PATH', '')}"}
        result = subprocess.run(
            ["cloud-mirror", "--help"],
            capture_output=True,
            text=True,
            env=env,
        )

        # Then: Success
        assert result.returncode == 0
        assert "cloud-mirror" in result.stdout.lower()
        assert "Mirror ZFS datasets" in result.stdout
```

### FI2: Wrapper works from different working directory

```python
def test_wrapper_from_different_cwd():
    """
    GIVEN wrapper script in /project/cloud-mirror
    WHEN invoked from /tmp (different cwd)
    THEN still finds package and runs correctly
    """
    # Given: Wrapper at known location
    wrapper = Path.cwd() / "cloud-mirror"
    assert wrapper.exists(), "Wrapper script must exist"

    # When: Invoke from different directory
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [str(wrapper), "--help"],
            cwd=tmpdir,  # Different working directory
            capture_output=True,
            text=True,
        )

        # Then: Success (package found via wrapper path, not cwd)
        assert result.returncode == 0
        assert "cloud-mirror" in result.stdout.lower()
```

### FI3: Wrapper with shebang runs directly

```python
def test_wrapper_shebang_execution():
    """
    GIVEN wrapper script with #!/usr/bin/env python3 shebang
    WHEN executed directly (not via python3 wrapper)
    THEN runs successfully
    """
    # Given: Wrapper script
    wrapper = Path.cwd() / "cloud-mirror"

    # Ensure executable bit set
    import stat

    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # When: Execute directly
    result = subprocess.run(
        [str(wrapper), "--help"],
        capture_output=True,
        text=True,
    )

    # Then: Success
    assert result.returncode == 0
```

## Capability Contribution

This feature enables capability-88 (CLI Configuration Management) by providing a user-friendly invocation method. Instead of `python3 -m cloud_mirror`, users can invoke `cloud-mirror` directly.

Integration points:

- Calls `cloud_mirror.main:main()` after setting up import path
- Works with feature-32 (Config Module) for finding config files
- Enables feature-76 (Profile Integration) to work from symlinked locations

## Completion Criteria

- [ ] All Level 1 tests pass (path resolution, sys.path manipulation)
- [ ] All Level 2 integration tests pass (symlink execution, cwd independence)
- [ ] `cloud-mirror` wrapper script created at project root
- [ ] Script has correct shebang and executable permissions
- [ ] Escalation rationale documented

**Note**: To see current stories in this feature, use `ls` or `find` to list story directories (e.g., `story-*`) within the feature's directory.
