# Story: Clone Tree Destruction

## Observable Outcome

Clone trees can be destroyed safely, with protection against accidentally destroying datasets not created by cloud-mirror.

## Functional Requirements

### FR1: Destroy clone tree recursively

```gherkin
GIVEN clone tree testpool/root.cloudmirror exists
AND it has our management property
WHEN destroy_clone_tree(clone_root, logger) called
THEN all clones are unmounted
AND all clones are destroyed
AND no remnants remain
```

### FR2: Refuse to destroy non-managed datasets

```gherkin
GIVEN dataset testpool/data.cloudmirror exists
BUT it lacks ch.srvr.cloudmirror:managed property
WHEN destroy_clone_tree called
THEN raises error
AND dataset is NOT destroyed
```

### FR3: Handle non-existent clone tree gracefully

```gherkin
GIVEN clone tree testpool/root.cloudmirror does NOT exist
WHEN destroy_clone_tree(clone_root, logger) called
THEN returns without error
AND logs that nothing to destroy
```

### FR4: Find stale clone trees

```gherkin
GIVEN stale clone tree testpool/root.cloudmirror exists (from failed run)
WHEN find_stale_clone(root_dataset, logger) called
THEN returns clone_root if it exists and is ours
THEN returns None if it doesn't exist
```

## Implementation Notes

- Use `zfs destroy -rf` to force unmount and recursive destroy
- Always verify management property before destruction
- Stale detection happens before clone tree creation
