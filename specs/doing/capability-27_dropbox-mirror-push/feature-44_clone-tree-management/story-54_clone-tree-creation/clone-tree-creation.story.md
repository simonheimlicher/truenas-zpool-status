# Story: Clone Tree Creation

## Observable Outcome

A complete clone tree can be created from a recursive snapshot, mirroring the original dataset structure with proper mountpoints.

## Functional Requirements

### FR1: Create clone tree from snapshot

```gherkin
GIVEN recursive snapshot testpool/root@snap with children:
  | dataset                |
  | testpool/root          |
  | testpool/root/child1   |
  | testpool/root/child2   |
WHEN create_clone_tree(root_dataset, datasets, snapshot_name, clone_root, clone_mountpoint, logger) called
THEN clone tree exists:
  | clone                            | mountpoint                     |
  | testpool/root.cloudmirror        | /testpool/root.cloudmirror     |
  | testpool/root.cloudmirror/child1 | /testpool/root.cloudmirror/child1 |
  | testpool/root.cloudmirror/child2 | /testpool/root.cloudmirror/child2 |
AND all clones are readonly
AND all clones have management property
```

### FR2: Handle altroot for TrueNAS

```gherkin
GIVEN pool with altroot=/mnt
AND desired clone mountpoint /mnt/testpool/data.cloudmirror
WHEN create_clone called
THEN zfs clone -o mountpoint=/testpool/data.cloudmirror (altroot stripped)
```

### FR3: Mount clones if not auto-mounted

```gherkin
GIVEN clone tree created
WHEN clones are not auto-mounted
THEN explicitly mount each clone
```

## Implementation Notes

- Clones are created in order (parent before children)
- Mountpoints must account for pool altroot
- ZFS may auto-mount clones; if not, mount explicitly
