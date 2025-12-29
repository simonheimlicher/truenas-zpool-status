# Story: Test Pool Creation

## Functional Requirements

### FR1: Test pool created from loopback file

```gherkin
GIVEN ZFS installed in Colima VM
WHEN test pool creation script executed
THEN 512MB sparse file created at /zfs-test/testpool.img
AND loopback device attached to file
AND ZFS pool "testpool" created on loopback device
AND pool is imported and ready for use
```

#### Files created/modified

1. `scripts/create-test-pool.sh` [new]: Script to create testpool from loopback file

**Test Validation:**

1. Integration test: `specs/doing/capability-10_docker-test-environment/feature-32_colima-zfs-environment/story-76_test-pool-creation/tests/test_pool_creation.py`

### FR2: Test pool survives VM restart

```gherkin
GIVEN testpool created from loopback file
WHEN VM stopped and restarted
THEN loopback file persists
AND pool can be re-imported with: zpool import -d /zfs-test testpool
```

### FR3: Multiple test datasets can coexist

```gherkin
GIVEN testpool exists
WHEN multiple datasets created:
  | dataset          |
  | testpool/test-a  |
  | testpool/test-b  |
  | testpool/test-c  |
THEN all datasets exist independently
AND each has its own mountpoint
```

### FR4: Dataset cleanup doesn't affect pool

```gherkin
GIVEN testpool with datasets testpool/test-a and testpool/test-b
WHEN testpool/test-a destroyed
THEN testpool/test-b still exists
AND testpool still healthy
```

## Quality Requirements

### QR1: Pool size sufficient for tests

**Requirement:** Pool must be large enough for test data
**Target:** 512MB sparse file (grows as needed)
**Validation:** Can create datasets with test files

### QR2: Sparse file efficiency

**Requirement:** Loopback file should not consume disk until used
**Target:** Initial file size near 0, grows with data
**Validation:** ls -lh shows small initial size

### QR3: Reproducible setup

**Requirement:** Pool creation should be idempotent
**Target:** Running script twice doesn't fail or corrupt
**Validation:** Script handles existing pool gracefully
