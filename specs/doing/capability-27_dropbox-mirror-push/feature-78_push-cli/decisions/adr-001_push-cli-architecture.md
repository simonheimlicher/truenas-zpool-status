# ADR-001: Push CLI Architecture

## Problem

Feature-78 requires a command-line interface that orchestrates the complete push workflow: validation, snapshot, clone, sync, cleanup. How should we structure the CLI to be testable, maintainable, and robust?

## Options Considered

### Option 1: Single run_push function

All workflow logic in one function with try/finally for cleanup.

### Option 2: Workflow state machine

Explicit state transitions with rollback handlers for each state.

### Option 3: Dependency-injected orchestrator

Orchestrator class that accepts operations as injected dependencies, enabling isolated testing.

## Decision

**We will use Option 3: Dependency-injected orchestrator.**

The orchestrator receives operations (validate, snapshot, clone, sync, cleanup) as injectable dependencies. This enables:

- Level 1 testing of orchestration logic with fake operations
- Level 2 testing with real ZFS/rclone operations
- Clear separation of concerns

## Rationale

The push workflow has 9 steps that must execute in order with cleanup on failure:

1. Validate dataset exists
2. Validate rclone config and remote
3. List datasets recursively
4. Create recursive snapshot
5. Create clone tree
6. Run rclone sync
7. Cleanup old versions (if --keep-versions)
8. Destroy clone tree (unless --keep-clone)
9. Destroy snapshot (unless --keep-snapshot)

Using dependency injection allows testing the orchestration logic (step ordering, cleanup on failure, dry-run behavior) at Level 1 without spinning up infrastructure. The actual ZFS/rclone operations are already tested by features 27, 44, and 61.

## Trade-offs Accepted

- More abstraction: Operations must be wrapped in a common interface
- More code: Separate orchestrator class vs inline logic
- Acceptable because: Testability is worth the abstraction cost

## Constraints

### Code Structure

```
cloud_mirror/
├── push.py           # PushOrchestrator, PushOperations protocol
├── zfs.py            # (existing) ZFS operations
└── rclone.py         # (existing) rclone operations

cloud-mirror.py       # CLI entry point using argparse
```

### PushOperations Protocol

```python
class PushOperations(Protocol):
    def validate_dataset(self, dataset: str) -> None: ...
    def validate_remote(self, remote: str, config: Path) -> None: ...
    def list_datasets(self, root: str) -> list[str]: ...
    def create_snapshot(self, datasets: list[str], name: str) -> None: ...
    def create_clone_tree(self, snapshot: str, datasets: list[str]) -> str: ...
    def sync(self, source: Path, dest: str, config: SyncConfig) -> SyncResult: ...
    def cleanup_versions(self, dest: str, keep: int, config: Path) -> CleanupResult: ...
    def destroy_clone(self, clone: str) -> None: ...
    def destroy_snapshot(self, datasets: list[str], name: str) -> None: ...
```

### Locking Strategy

- Lock file: `/var/run/cloud-mirror/{pool}.lock` (production) or `~/.cache/cloud-mirror/{pool}.lock` (dev)
- Acquisition: `fcntl.flock(LOCK_EX | LOCK_NB)`
- Scope: Per-pool, not per-dataset (prevents conflicting operations on same pool)
- Cleanup: Released on process exit (via context manager)

### Error Handling

```python
class PushError(Exception):
    """Base exception for push failures."""


class ValidationError(PushError):
    """Dataset or remote validation failed."""


class SnapshotError(PushError):
    """Snapshot creation/destruction failed."""


class CloneError(PushError):
    """Clone tree creation/destruction failed."""


class SyncError(PushError):
    """Rclone sync failed."""


class LockError(PushError):
    """Could not acquire lock (concurrent operation)."""
```

## Testing Strategy

### Level Assignments

| Component          | Level        | Justification                         |
| ------------------ | ------------ | ------------------------------------- |
| Argument parsing   | 1 (Unit)     | Pure argparse logic, no external deps |
| Orchestrator logic | 1 (Unit)     | DI allows fake operations             |
| Lock acquisition   | 2 (VM)       | Needs real filesystem                 |
| Full workflow      | 2 (VM)       | Real ZFS + local rclone backend       |
| Dropbox sync       | 3 (Internet) | Real Dropbox for E2E                  |

### Escalation Rationale

- Level 1→2: Unit tests prove orchestration order, but need real ZFS to verify clone trees work
- Level 2→3: VM tests prove local sync, but need Dropbox to verify rate limiting and OAuth

### Testing Principles

- NO MOCKING: Use dependency injection for all external dependencies
- Behavior only: Test observable outcomes (files synced, cleanup occurred)
- Minimum level: Orchestration logic tested at Level 1, integration at Level 2

## Stories to Implement

This ADR informs the following stories (to be created):

1. **story-32_cli-argument-parsing**: Parse arguments per FI1, FI2
2. **story-54_push-orchestrator**: Implement PushOrchestrator per FI3, FI4
3. **story-76_push-locking**: Implement locking per FI5
4. **story-89_push-integration**: Wire everything together, FI6 (dry-run)
