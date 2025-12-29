# Feature: Clone Tree Management

## Observable Outcome

Clone trees are created from snapshots to provide an immutable, consistent filesystem view for sync operations. Clones are properly identified as ours and safely destroyed after use.

## Feature Integration Tests

### FI1: Clone tree mirrors dataset structure

```gherkin
GIVEN snapshot testpool/root@snap with children:
  | dataset                |
  | testpool/root          |
  | testpool/root/child1   |
  | testpool/root/child2   |
WHEN create_clone_tree called
THEN clone tree exists:
  | clone                           | mountpoint                    |
  | testpool/root.cloudmirror       | /testpool/root.cloudmirror    |
  | testpool/root.cloudmirror/child1| /testpool/root.cloudmirror/child1 |
  | testpool/root.cloudmirror/child2| /testpool/root.cloudmirror/child2 |
AND all clones are readonly
AND all clones have property ch.srvr.cloudmirror:managed=true
```

### FI2: Clone tree accessible as filesystem

```gherkin
GIVEN clone tree created from snapshot with files
WHEN filesystem operations performed on clone mountpoint
THEN files are readable
AND directory structure matches original
AND symlinks are preserved
```

### FI3: Clone tree destroyed with force

```gherkin
GIVEN clone tree testpool/root.cloudmirror exists
WHEN destroy_clone_tree(testpool/root.cloudmirror, logger) called
THEN all clones are unmounted
AND all clones are destroyed
AND no remnants remain
```

### FI4: Only our clones are destroyed

```gherkin
GIVEN dataset testpool/root.cloudmirror exists
BUT it lacks ch.srvr.cloudmirror:managed property (not ours)
WHEN is_our_clone checked
THEN returns False
AND destroy_clone_tree refuses to destroy it
```

### FI5: Stale clone tree detected and cleaned

```gherkin
GIVEN stale clone tree testpool/root.cloudmirror exists (from failed run)
AND it has our managed property
WHEN push operation starts
THEN stale clone tree is destroyed
AND new clone tree created from fresh snapshot
```

## Capability Contribution

The clone tree provides the immutable source for rclone sync. Without clone trees, traversing `.zfs/snapshot/` would show live child dataset mountpoints instead of snapshot contents, breaking consistency for nested datasets.
