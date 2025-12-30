# Story: ZFS Dataset Fixtures

## Functional Requirements

### FR1: ZFS dataset fixture creates isolated dataset (FI1)

```gherkin
GIVEN pytest with conftest.py loaded
WHEN a test uses the zfs_dataset fixture
THEN a unique dataset (testpool/test-{uuid}) is created before the test
AND the dataset is destroyed after the test completes
AND no interference occurs with other concurrent tests
```

### FR2: Nested dataset fixture creates parent and children (FI2)

```gherkin
GIVEN pytest with conftest.py loaded
WHEN a test uses the zfs_dataset_with_children fixture
THEN root dataset and child1, child2 are created
AND all datasets are destroyed after the test
```

### FR3: Fixtures skip gracefully when ZFS unavailable (FI4)

```gherkin
GIVEN pytest running without ZFS (VM not running)
WHEN a test using zfs_dataset fixture runs
THEN the test is skipped with clear message
AND non-ZFS tests continue to run
```

## Files Created/Modified

1. `tests/conftest.py`: `zfs_dataset`, `zfs_dataset_with_children`, `ensure_vm_running`, `ensure_pool_exists` fixtures
