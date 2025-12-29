# Feature: ZFS Snapshot Operations

## Observable Outcome

Recursive ZFS snapshots can be created and destroyed reliably across dataset hierarchies. Stale snapshots from failed runs are detected and cleaned up automatically.

## Feature Integration Tests

### FI1: Recursive snapshot captures all datasets

```gherkin
GIVEN ZFS dataset testpool/root with children:
  | dataset                |
  | testpool/root          |
  | testpool/root/child1   |
  | testpool/root/child2   |
WHEN create_recursive_snapshot(testpool/root, "test-snap", logger) called
THEN snapshots exist:
  | snapshot                        |
  | testpool/root@test-snap         |
  | testpool/root/child1@test-snap  |
  | testpool/root/child2@test-snap  |
```

### FI2: Recursive snapshot destruction removes all

```gherkin
GIVEN recursive snapshot testpool/root@test-snap exists
WHEN destroy_recursive_snapshot(testpool/root, "test-snap", logger) called
THEN no snapshots with name "test-snap" remain under testpool/root
```

### FI3: Stale snapshot detected and cleaned before new snapshot

```gherkin
GIVEN stale snapshot testpool/root@cloudmirror-old exists (from previous failed run)
WHEN create_recursive_snapshot(testpool/root, "cloudmirror-new", logger) called
THEN stale snapshot is destroyed first
AND new snapshot is created successfully
```

### FI4: Partial stale snapshots cleaned up

```gherkin
GIVEN stale snapshot exists only on child (testpool/root/child1@cloudmirror-old)
BUT not on root (testpool/root@cloudmirror-old does not exist)
WHEN create_recursive_snapshot called
THEN orphaned child snapshot is destroyed
AND new recursive snapshot created on all datasets
```

## Capability Contribution

Snapshots provide the atomic, point-in-time consistency guarantee for push operations. Without reliable snapshot operations, the clone tree cannot be created from a consistent state.
