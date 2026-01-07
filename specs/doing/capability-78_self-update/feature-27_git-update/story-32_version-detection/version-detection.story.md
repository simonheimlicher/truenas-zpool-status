# Story: Version Detection and Update Check

## ⚠️ Project-Specific Constraints

- **Real git fixtures required**: Tests use actual git repos in `tmp_path`, not mocks (per ADR-003)
- **Zero runtime dependencies**: Only stdlib subprocess calls, no GitPython or similar
- **Read-only operations**: This story contains no state-modifying operations

## Functional Requirements

### FR1: Detect git installation

```gherkin
GIVEN cloud-mirror may be installed via git clone or file copy
WHEN is_git_installation() is called
THEN it returns True if .git directory exists
AND returns False if no .git directory
AND no git commands are executed (filesystem check only)
```

#### Files created/modified

1. `cloud_mirror/update.py` [new]: Core update module with version detection functions

**Test Validation:**

1. Unit test: `specs/doing/capability-78_self-update/feature-27_git-update/story-32_version-detection/tests/test_git_installation_detection.py`

### FR2: Get installed version from git

```gherkin
GIVEN cloud-mirror is installed in a git repository
AND the repo has tags like v0.1.0, v0.2.0
WHEN get_installed_version() is called
THEN it executes "git describe --tags --always"
AND returns the version string (e.g., "v0.1.0" or "v0.1.0-3-gabcdef")
AND if git command fails, returns __version__ from cloud_mirror/__init__.py
```

#### Files created/modified

1. `cloud_mirror/update.py` [modify]: Add `get_installed_version()` function

**Test Validation:**

1. Unit test: `specs/doing/capability-78_self-update/feature-27_git-update/story-32_version-detection/tests/test_version_detection.py`

### FR3: Fetch remote version

```gherkin
GIVEN a git repository with a remote configured
WHEN get_remote_version() is called
THEN it executes "git fetch origin --tags --quiet"
AND executes "git describe --tags --always origin/main"
AND returns the remote version string
AND if network fails, returns None with error message
```

#### Files created/modified

1. `cloud_mirror/update.py` [modify]: Add `get_remote_version()` function

**Test Validation:**

1. Unit test: `specs/doing/capability-78_self-update/feature-27_git-update/story-32_version-detection/tests/test_remote_version_check.py`
2. Integration test (network failure): `specs/doing/capability-78_self-update/feature-27_git-update/story-32_version-detection/tests/test_network_error_handling.py`

### FR4: Compare versions and determine if update available

```gherkin
GIVEN local version is v0.1.0 and remote version is v0.2.0
WHEN check_for_update() is called
THEN it calls is_git_installation() first
AND if not git installation, returns None
AND if git installation, calls get_installed_version() and get_remote_version()
AND compares commit hashes to determine if update is available
AND returns UpdateStatus(current="v0.1.0", remote="v0.2.0", available=True)
```

#### Files created/modified

1. `cloud_mirror/update.py` [modify]: Add `check_for_update()` orchestrator function
2. `cloud_mirror/update.py` [modify]: Add `UpdateStatus` dataclass

**Test Validation:**

1. Integration test: `specs/doing/capability-78_self-update/feature-27_git-update/story-32_version-detection/tests/test_update_detection.py`

## Architectural Requirements

### Relevant ADRs

1. `specs/decisions/adr-002_git-based-self-update.md` - Git-based update decision
2. `specs/doing/capability-78_self-update/decisions/adr-003_real-git-test-fixtures.md` - Test fixtures using real git

### Design Decisions

**Module structure:**
```python
# cloud_mirror/update.py

from dataclasses import dataclass
from pathlib import Path
import subprocess

@dataclass
class UpdateStatus:
    """Status of update check."""
    current_version: str | None
    remote_version: str | None
    update_available: bool
    error: str | None = None

def is_git_installation(repo_path: Path | None = None) -> bool:
    """Check if cloud-mirror is installed via git."""

def get_installed_version(repo_path: Path | None = None) -> str | None:
    """Get current version using git describe."""

def get_remote_version(repo_path: Path | None = None) -> str | None:
    """Fetch and get remote version from origin/main."""

def check_for_update(repo_path: Path | None = None) -> UpdateStatus | None:
    """Check if update is available. Returns None for non-git installs."""
```

**Git command patterns:**
- Use `subprocess.run()` with `capture_output=True, text=True`
- Check `returncode` for success/failure
- Parse stdout for version strings
- Handle stderr for error messages

## Quality Requirements

### QR1: Performance

**Requirement:** Version detection must be fast to avoid delaying sync operations
**Target:** < 100ms for local version check, < 2s for remote check with network
**Validation:** pytest benchmark or simple time.time() measurements in tests

### QR2: Network failure resilience

**Requirement:** Network failures must not raise exceptions or block execution
**Target:** All network-dependent functions return None or error status, never raise
**Validation:** Test with simulated network failure (invalid remote URL)

### QR3: Git command safety

**Requirement:** Git commands must not modify repository state
**Target:** Only read-only git commands (describe, fetch with no merge/pull)
**Validation:** Test verifies working directory unchanged after operations

### QR4: Non-git installation handling

**Requirement:** Non-git installations must be detected gracefully
**Target:** No git subprocess calls attempted for non-git installations
**Validation:** Test with directory lacking .git, verify no subprocess calls made

### Documentation

1. `cloud_mirror/update.py` - Comprehensive docstrings for all public functions
2. README.md will be updated in later stories when full update flow is complete
