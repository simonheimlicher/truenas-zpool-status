# Capability: Dropbox Mirror Push

## Success Metric

**Quantitative Target:**

- **Baseline**: `dropbox-push.py` works but has no automated tests; cannot verify correctness without manual testing on TrueNAS
- **Target**: `cloud-mirror.py` with push functionality, fully tested with ZFS integration tests
- **Measurement**: All push integration tests pass; `cloud-mirror.py dataset remote` produces identical results to `dropbox-push.py`

## Capability Integration Tests

### EI1: Full push workflow syncs files to remote

```gherkin
GIVEN ZFS dataset testpool/source with files:
  | path              | content         |
  | file1.txt         | content of file1 |
  | subdir/file2.txt  | content of file2 |
AND rclone remote testremote: configured
WHEN cloud-mirror.py testpool/source testremote:backup executed
THEN files appear on remote at testremote:backup/
AND snapshot testpool/source@cloudmirror-TIMESTAMP is created and destroyed
AND clone tree testpool/source.cloudmirror is created and destroyed
```

### EI2: Nested datasets are handled correctly

```gherkin
GIVEN ZFS dataset testpool/parent with children:
  | dataset                   | files          |
  | testpool/parent           | root.txt       |
  | testpool/parent/child1    | child1.txt     |
  | testpool/parent/child2    | child2.txt     |
WHEN cloud-mirror.py testpool/parent testremote:backup executed
THEN all files from all datasets appear on remote
AND directory structure matches mountpoint structure
```

### EI3: Symlinks preserved as .rclonelink files

```gherkin
GIVEN ZFS dataset with symlink: link.txt -> target.txt
WHEN cloud-mirror.py pushes to remote
THEN remote contains link.txt.rclonelink with content "target.txt"
```

### EI4: Version backup preserves changed files

```gherkin
GIVEN remote already has files from previous push
AND local files have changed
WHEN cloud-mirror.py --keep-versions 3 executed
THEN changed/deleted files moved to .versions/TIMESTAMP/
AND only 3 most recent versions retained
```

## System Integration

This capability extracts the existing `dropbox-push.py` functionality into `cloud-mirror.py` with proper test coverage. It depends on Capability-10 (Colima Test Environment) for running ZFS integration tests.

The push functionality serves as the foundation for Capability-54 (Dropbox Mirror Pull), which adds bidirectional sync by detecting argument order.
