# Story: List Datasets Recursively

## Functional Requirements

### FR1: Enumerate all datasets under root

```gherkin
GIVEN ZFS dataset testpool/root with children:
  | dataset                |
  | testpool/root          |
  | testpool/root/child1   |
  | testpool/root/child2   |
WHEN list_datasets_recursive(testpool/root, logger) called
THEN returns list:
  | dataset                |
  | testpool/root          |
  | testpool/root/child1   |
  | testpool/root/child2   |
AND root dataset is first in list
```

### FR2: Handle single dataset (no children)

```gherkin
GIVEN ZFS dataset testpool/single with no children
WHEN list_datasets_recursive(testpool/single, logger) called
THEN returns [testpool/single]
```

### FR3: Handle deeply nested datasets

```gherkin
GIVEN ZFS dataset testpool/a/b/c/d (4 levels deep)
WHEN list_datasets_recursive(testpool/a, logger) called
THEN returns all datasets in hierarchy
AND maintains parent-child ordering
```

## Files Created/Modified

1. `cloud_mirror/zfs.py` [new]: ZFS utility functions
