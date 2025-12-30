# Story: Create Recursive Snapshot

## Functional Requirements

### FR1: Create snapshot on all datasets (FI1)

```gherkin
GIVEN ZFS dataset testpool/root with children
WHEN create_recursive_snapshot(testpool/root, "test-snap", logger) called
THEN snapshot exists on root and all children with same name
```

### FR2: Clean stale snapshots before creating (FI3)

```gherkin
GIVEN stale snapshot testpool/root@cloudmirror-old exists
WHEN create_recursive_snapshot(testpool/root, "cloudmirror-new", logger) called
THEN stale snapshot destroyed first
AND new snapshot created successfully
```

### FR3: Clean partial stale snapshots (FI4)

```gherkin
GIVEN stale snapshot on child only (testpool/root/child@cloudmirror-old)
BUT not on root (testpool/root@cloudmirror-old does not exist)
WHEN create_recursive_snapshot called
THEN orphaned child snapshot destroyed
AND new recursive snapshot created on all datasets
```

## Files Created/Modified

1. `cloud_mirror/zfs.py` [modify]: add create_recursive_snapshot, find_stale_snapshots
