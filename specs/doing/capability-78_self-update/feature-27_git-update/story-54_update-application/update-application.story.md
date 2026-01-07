# Story: Safe Update Application

## ⚠️ Project-Specific Constraints

- **Depends on story-32**: Requires version detection functions
- **Real git fixtures required**: Tests use actual git repos with commits/tags
- **State-modifying operations**: This story changes git repository state
- **Atomic updates required**: Use `git pull --ff-only` for transactional updates

## Functional Requirements

### FR1: Check for uncommitted changes before update

```gherkin
GIVEN a git repository with uncommitted file changes
WHEN apply_update() is called
THEN it executes "git status --porcelain"
AND detects non-empty output (uncommitted changes)
AND aborts update before git pull
AND returns UpdateResult(success=False, error="Uncommitted changes detected")
AND working directory remains unchanged
```

#### Files created/modified

1. `cloud_mirror/update.py` [modify]: Add `has_uncommitted_changes()` helper function
2. `cloud_mirror/update.py` [modify]: Add `UpdateResult` dataclass

**Test Validation:**

1. Integration test: `specs/doing/capability-78_self-update/feature-27_git-update/story-54_update-application/tests/test_dirty_repo_blocks_update.py`

### FR2: Apply update atomically using git pull

```gherkin
GIVEN a clean git repository (no uncommitted changes)
AND remote has newer commits (update available)
WHEN apply_update() is called
THEN it calls has_uncommitted_changes() first (returns False)
AND executes "git fetch origin main"
AND executes "git pull --ff-only origin main"
AND local HEAD moves to remote commit
AND returns UpdateResult(success=True, old_version="v0.1.0", new_version="v0.2.0")
```

#### Files created/modified

1. `cloud_mirror/update.py` [modify]: Add `apply_update()` function

**Test Validation:**

1. Integration test: `specs/doing/capability-78_self-update/feature-27_git-update/story-54_update-application/tests/test_update_application.py`

### FR3: Handle git pull failures gracefully

```gherkin
GIVEN git pull --ff-only fails (e.g., non-fast-forward merge needed)
WHEN apply_update() is called
THEN git pull returns non-zero exit code
AND function catches the failure
AND returns UpdateResult(success=False, error="Git pull failed: <stderr>")
AND working directory remains at original commit
```

#### Files created/modified

1. `cloud_mirror/update.py` [modify]: Error handling in `apply_update()`

**Test Validation:**

1. Integration test: `specs/doing/capability-78_self-update/feature-27_git-update/story-54_update-application/tests/test_update_failure_handling.py`

## Architectural Requirements

### Relevant ADRs

1. `specs/decisions/adr-002_git-based-self-update.md` - Atomic updates via git pull --ff-only

### Design Decisions

**Module additions:**
```python
# cloud_mirror/update.py

@dataclass
class UpdateResult:
    """Result of update application."""
    success: bool
    old_version: str | None = None
    new_version: str | None = None
    error: str | None = None

def has_uncommitted_changes(repo_path: Path | None = None) -> bool:
    """Check if working directory has uncommitted changes."""
    # Uses: git status --porcelain

def apply_update(repo_path: Path | None = None) -> UpdateResult:
    """
    Apply update by pulling from origin/main.

    Returns UpdateResult with success/failure status.
    Aborts if uncommitted changes detected.
    Uses --ff-only to ensure atomic updates.
    """
```

**Git command sequence:**
1. `git status --porcelain` - Check for dirty state
2. `git fetch origin main` - Fetch remote commits
3. `git pull --ff-only origin main` - Apply update atomically

**Error scenarios:**
- Dirty working directory → abort before pull
- Network failure during fetch → return error
- Non-fast-forward merge → git pull fails, return error

## Quality Requirements

### QR1: Atomicity

**Requirement:** Updates must be atomic - either fully applied or not at all
**Target:** No partial updates possible (git pull --ff-only ensures this)
**Validation:** Test verifies that failed updates leave repo in original state

### QR2: Safety checks

**Requirement:** Never overwrite uncommitted local changes
**Target:** 100% detection of dirty working directories before any git pull
**Validation:** Test with various uncommitted change types (modified, added, deleted files)

### QR3: Error reporting

**Requirement:** Update failures must provide actionable error messages
**Target:** Error messages include git stderr output for debugging
**Validation:** Test verifies error messages contain git command output

### QR4: Idempotency

**Requirement:** Applying update when already up-to-date is safe (no-op)
**Target:** git pull with no new commits succeeds without errors
**Validation:** Test calls apply_update() twice, second call succeeds

### Documentation

1. `cloud_mirror/update.py` - Docstrings for `apply_update()` and helpers
2. Inline comments explaining `--ff-only` rationale
