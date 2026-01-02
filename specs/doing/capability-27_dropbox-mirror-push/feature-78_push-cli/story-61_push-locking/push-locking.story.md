# Story: Push Locking

## What Changes

Implement filesystem-based locking to prevent concurrent push operations on the same pool.

## Functional Requirements

### FR1: Lock acquired before workflow

```gherkin
GIVEN push command for testpool/data
WHEN workflow starts
THEN lock acquired for "testpool" (pool name)
AND lock file created at lock directory
```

### FR2: Concurrent push fails immediately

```gherkin
GIVEN push operation running on testpool/data
WHEN second push attempted on testpool/anything
THEN second operation fails with LockError
AND error message indicates lock conflict
AND first operation continues unaffected
```

### FR3: Lock released on completion

```gherkin
GIVEN push operation holding lock
WHEN operation completes (success or failure)
THEN lock is released
AND subsequent push can acquire lock
```

### FR4: Lock file location

```gherkin
GIVEN XDG_RUNTIME_DIR or /var/run/cloud-mirror exists
WHEN lock needed
THEN lock file at {runtime_dir}/cloud-mirror/{pool}.lock
OR fallback to ~/.cache/cloud-mirror/{pool}.lock
```

## Testing Level

**Level 2 (VM)**: Needs real filesystem for lock files and concurrent process testing.

## Implementation Notes

- Use `fcntl.flock(LOCK_EX | LOCK_NB)` for non-blocking exclusive lock
- Extract pool name from dataset: `dataset.split("/")[0]`
- Context manager for automatic cleanup
- Create lock directory if not exists
- Graceful fallback on permission errors
