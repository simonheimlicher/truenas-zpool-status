# Story: Destroy Recursive Snapshot

## Functional Requirements

### FR1: Destroy snapshot on all datasets (FI2)

```gherkin
GIVEN recursive snapshot testpool/root@test-snap exists
WHEN destroy_recursive_snapshot(testpool/root, "test-snap", logger) called
THEN no snapshots with name "test-snap" remain under testpool/root
```

### FR2: Handle missing snapshot gracefully

```gherkin
GIVEN snapshot testpool/root@nonexistent does not exist
WHEN destroy_recursive_snapshot called
THEN no error raised
AND warning logged
```

## Files Created/Modified

1. `cloud_mirror/zfs.py` [modify]: add destroy_recursive_snapshot
