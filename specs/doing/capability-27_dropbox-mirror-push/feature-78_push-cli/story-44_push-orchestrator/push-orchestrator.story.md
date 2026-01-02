# Story: Push Orchestrator

## What Changes

Implement PushOrchestrator that coordinates the push workflow steps using dependency injection.

## Functional Requirements

### FR1: Workflow executes in correct order

```gherkin
GIVEN valid dataset and remote
WHEN run_push(dataset, remote, config) called
THEN workflow executes in order:
  1. Validate dataset exists
  2. Validate rclone config and remote
  3. List datasets recursively
  4. Create recursive snapshot
  5. Create clone tree
  6. Run rclone sync
  7. Cleanup old versions (if keep_versions > 0)
  8. Destroy clone tree (unless keep_clone)
  9. Destroy snapshot (unless keep_snapshot)
```

### FR2: Cleanup occurs on sync failure

```gherkin
GIVEN push operation where rclone sync fails at step 6
WHEN SyncError is raised
THEN clone tree is destroyed (step 8)
AND snapshot is destroyed (step 9)
AND SyncError is re-raised
```

### FR3: Cleanup skipped when flags set

```gherkin
GIVEN keep_clone=True and keep_snapshot=True
WHEN push completes (success or failure)
THEN clone tree is NOT destroyed
AND snapshot is NOT destroyed
```

### FR4: PushOperations protocol

```gherkin
GIVEN PushOperations protocol defined
WHEN orchestrator instantiated
THEN accepts any implementation of the protocol
AND fake implementations work for testing
```

## Testing Level

**Level 1 (Unit)**: Use fake PushOperations to verify orchestration logic, step ordering, and cleanup behavior.

**Level 2 (VM)**: Use real ZFS + local rclone to verify end-to-end workflow.

## Implementation Notes

- PushOrchestrator class with run() method
- PushOperations Protocol for dependency injection
- RealPushOperations implementation wrapping zfs.py + rclone.py
- Use try/finally for cleanup guarantee
- Return PushResult with success/failure details
