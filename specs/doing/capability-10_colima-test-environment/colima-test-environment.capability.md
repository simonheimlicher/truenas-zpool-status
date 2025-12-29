# Capability: Colima Test Environment

## Success Metric

**Quantitative Target:**

- **Baseline**: No automated testing possible without TrueNAS hardware; manual testing requires copying scripts to TrueNAS
- **Target**: Full ZFS + rclone test suite runs locally on macOS via Colima
- **Measurement**: `pytest tests/ -m zfs` passes all ZFS integration tests in Colima VM

## Capability Integration Tests

### EI1: ZFS operations work in Colima VM

```gherkin
GIVEN Colima VM is running with Ubuntu and ZFS installed
AND a test ZFS pool exists
WHEN pytest runs ZFS integration tests
THEN all ZFS operations (create, snapshot, clone, destroy) succeed
AND tests complete without manual intervention
```

### EI2: rclone operations work with mock remote

```gherkin
GIVEN rclone is installed in test environment
AND a local backend mock remote is configured
WHEN pytest runs rclone integration tests
THEN files sync correctly to/from mock remote
AND symlinks are preserved via .rclonelink files
```

### EI3: Full sync workflow testable locally

```gherkin
GIVEN Colima VM with ZFS pool and rclone configured
WHEN cloud-mirror.py push or pull operations are tested
THEN complete workflow executes with real ZFS and mock rclone remote
AND cleanup occurs correctly after tests
```

## System Integration

This capability provides the foundation for testing Capability-27 (Dropbox Push) and Capability-54 (Dropbox Mirror Pull). Without a working test environment, development of sync functionality cannot proceed with confidence.

The test environment must:
- Run on macOS development machines (Apple Silicon)
- Provide real ZFS operations (not mocked)
- Use mock rclone remotes (no actual Dropbox connection needed)
- Support both unit tests (fast, no ZFS) and integration tests (require ZFS)
