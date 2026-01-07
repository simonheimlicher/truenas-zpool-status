# Story: Post-Update Process Re-execution

## ⚠️ Project-Specific Constraints

- **Depends on story-54**: Requires `apply_update()` to work first
- **Platform-specific behavior**: Uses `os.execv()` which replaces current process
- **Testing challenges**: Cannot test actual process replacement easily (process terminates)

## Functional Requirements

### FR1: Re-execute process with updated code

```gherkin
GIVEN an update has been applied successfully (new code on disk)
AND current process is running old code
WHEN reexec_with_new_code() is called with original command-line args
THEN it constructs command: [sys.executable, "-m", "cloud_mirror", ...args]
AND calls os.execv(sys.executable, command)
AND current process is replaced with new Python interpreter
AND new process runs updated code
```

#### Files created/modified

1. `cloud_mirror/update.py` [modify]: Add `reexec_with_new_code()` function

**Test Validation:**

1. Unit test: `specs/doing/capability-78_self-update/feature-27_git-update/story-76_process-reexecution/tests/test_reexec_command_construction.py` - Test command construction only (mock os.execv)
2. Integration test: Cannot fully test process replacement (would terminate test process)

### FR2: Preserve command-line arguments during re-execution

```gherkin
GIVEN original command was "cloud-mirror push tank/data dropbox:backup --config /path/to/config"
WHEN reexec_with_new_code() is called
THEN sys.argv is captured before re-execution
AND new process receives same arguments: ["cloud-mirror", "push", "tank/data", "dropbox:backup", "--config", "/path/to/config"]
AND sync operation proceeds with same parameters
```

#### Files created/modified

1. `cloud_mirror/update.py` [modify]: Argument preservation logic in `reexec_with_new_code()`

**Test Validation:**

1. Unit test: `specs/doing/capability-78_self-update/feature-27_git-update/story-76_process-reexecution/tests/test_argument_preservation.py`

### FR3: Handle re-execution failures gracefully

```gherkin
GIVEN os.execv() might fail (e.g., invalid Python path)
WHEN reexec_with_new_code() is called
AND os.execv() raises OSError
THEN exception is caught
AND error is logged
AND function returns normally without crashing
AND caller can handle failure (e.g., continue with old code)
```

#### Files created/modified

1. `cloud_mirror/update.py` [modify]: Error handling wrapper for `os.execv()`

**Test Validation:**

1. Unit test: `specs/doing/capability-78_self-update/feature-27_git-update/story-76_process-reexecution/tests/test_reexec_error_handling.py` - Mock os.execv to raise OSError

## Architectural Requirements

### Relevant ADRs

1. `specs/decisions/adr-002_git-based-self-update.md` - Re-execution pattern for applying updates

### Design Decisions

**Module additions:**
```python
# cloud_mirror/update.py

import os
import sys
import logging

logger = logging.getLogger(__name__)

def reexec_with_new_code() -> None:
    """
    Re-execute cloud-mirror with updated code.

    Uses os.execv() to replace current process with new Python interpreter.
    Preserves command-line arguments from sys.argv.

    Note: This function does not return if successful (process is replaced).
    On failure, logs error and returns normally.
    """
    try:
        # Construct command: [python, -m, cloud_mirror, ...original_args]
        args = [sys.executable, "-m", "cloud_mirror"] + sys.argv[1:]

        logger.info(f"Re-executing with updated code: {' '.join(args)}")

        # Replace current process (does not return)
        os.execv(sys.executable, args)

    except OSError as e:
        logger.error(f"Failed to re-execute: {e}")
        # Return normally, caller can decide how to handle
```

**Re-execution flow:**
1. `apply_update()` succeeds → new code on disk
2. Call `reexec_with_new_code()`
3. `os.execv()` replaces process
4. New process starts from `cloud_mirror.main:main()`
5. Proceeds with original sync operation

**Why os.execv():**
- Atomically replaces process (no subprocess management)
- Preserves PID (important for cron jobs and logging)
- Clean transition (no old process lingering)

## Quality Requirements

### QR1: Argument preservation

**Requirement:** All command-line arguments must be preserved during re-execution
**Target:** 100% of original arguments passed to new process
**Validation:** Unit test compares constructed command against original sys.argv

### QR2: Testing strategy

**Requirement:** Test command construction without actually replacing process
**Target:** Mock `os.execv()` to verify it would be called with correct arguments
**Validation:** Use `unittest.mock.patch` to intercept os.execv call

### QR3: Error resilience

**Requirement:** Re-execution failures must not crash the application
**Target:** Graceful fallback - log error and continue with current code
**Validation:** Test with mocked OSError, verify no exception propagates

### QR4: Logging

**Requirement:** Re-execution attempt must be logged for debugging
**Target:** INFO-level log before os.execv, ERROR-level if it fails
**Validation:** Test verifies log messages are emitted

### Documentation

1. `cloud_mirror/update.py` - Comprehensive docstring explaining re-execution pattern
2. Inline comment explaining why os.execv is used (vs subprocess or restart)
3. README.md - Will be updated when full update flow is integrated in feature-54/feature-76
