# Feature: Git-Based Update

## Observable Outcome

cloud-mirror can detect when a newer version exists on GitHub, fetch it via git, and apply the update atomically before running sync operations.

## Feature Integration Tests

### FI1: Update detection compares local and remote versions

GIVEN a git repository with cloud-mirror installed
AND the local version is v0.1.0 (tagged)
AND the remote has commits for v0.2.0 (tagged)
WHEN `check_for_update()` is called
THEN it returns `UpdateStatus(current="v0.1.0", remote="v0.2.0", available=True)`
AND no git state is modified (read-only operation)

### FI2: Update application is atomic via git pull

GIVEN update is available (remote ahead of local)
AND working directory is clean (no uncommitted changes)
WHEN `apply_update()` is called
THEN `git fetch origin` executes successfully
AND `git pull --ff-only origin main` executes successfully
AND local HEAD moves to remote commit
AND function returns `UpdateResult(success=True, old="v0.1.0", new="v0.2.0")`

### FI3: Dirty working directory prevents update

GIVEN a git repository with uncommitted changes
AND an update is available
WHEN `apply_update()` is called
THEN update is aborted before git pull
AND function returns `UpdateResult(success=False, error="Uncommitted changes detected")`
AND working directory remains unchanged

### FI4: Non-git installation detected gracefully

GIVEN cloud-mirror installed by copying files (no .git directory)
WHEN `is_git_installation()` is called
THEN it returns False
AND `check_for_update()` returns None
AND no git commands are attempted

### FI5: Network failure doesn't block execution

GIVEN git repository with no network connectivity
WHEN `check_for_update()` is called
THEN git fetch fails
AND function returns `UpdateStatus(available=False, error="Network error")`
AND exception is not raised (graceful degradation)

### FI6: Re-execution uses new code after update

GIVEN update applied successfully
WHEN `reexec_with_new_code()` is called
THEN `os.execv(sys.executable, [sys.executable, "-m", "cloud_mirror", ...])` is invoked
AND process is replaced with new Python interpreter
AND original arguments are preserved

## Capability Contribution

This feature provides the core update mechanism for the self-update capability. It integrates with:

- **Feature 54 (Update CLI)**: Provides the backend for `--update` and `--check-update` flags
- **Feature 76 (Update Orchestration)**: Called during startup flow to apply updates before sync

The git-based approach ensures atomic updates, built-in rollback, and transparency - critical for safe automatic updates in production environments.

**Note**: To see current stories in this feature, use `ls` or `find` to list story directories (e.g., `story-*`) within the feature's directory.
