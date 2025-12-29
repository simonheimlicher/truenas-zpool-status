# Feature: Pytest Fixtures

## Observable Outcome

Reusable pytest fixtures provide isolated ZFS datasets and sample files for each test, with automatic cleanup after test completion.

## Feature Integration Tests

### FI1: ZFS dataset fixture creates isolated dataset

```gherkin
GIVEN pytest with conftest.py loaded
WHEN a test uses the zfs_dataset fixture
THEN a unique dataset (testpool/test-{uuid}) is created before the test
AND the dataset is destroyed after the test completes
AND no interference occurs with other concurrent tests
```

### FI2: Nested dataset fixture creates parent and children

```gherkin
GIVEN pytest with conftest.py loaded
WHEN a test uses the zfs_dataset_with_children fixture
THEN root dataset and child1, child2 are created
AND all datasets are destroyed after the test
```

### FI3: Sample files fixture populates dataset

```gherkin
GIVEN a test using both zfs_dataset and sample_files fixtures
WHEN the test runs
THEN the dataset mountpoint contains:
  - file1.txt with known content
  - subdir/file2.txt with known content
  - symlink.txt pointing to file1.txt
```

### FI4: Fixtures skip gracefully when ZFS unavailable

```gherkin
GIVEN pytest running without ZFS (e.g., in Docker without Colima)
WHEN a test marked with @pytest.mark.zfs runs
THEN the test is skipped with clear message
AND non-ZFS tests continue to run
```

## Capability Contribution

This feature enables test isolation and repeatability. Each test gets a clean ZFS environment, preventing test pollution and enabling parallel test execution.
