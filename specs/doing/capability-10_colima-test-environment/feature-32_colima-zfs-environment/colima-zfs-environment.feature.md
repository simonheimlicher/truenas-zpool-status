# Feature: Colima ZFS Environment

## Observable Outcome

Developers can start a Colima VM on macOS that provides a working ZFS environment for running integration tests. The VM automatically creates a test ZFS pool on startup.

## Feature Integration Tests

### FI1: Colima VM starts with ZFS available

```gherkin
GIVEN Colima is installed via Homebrew
AND Ubuntu VM template is used
WHEN colima start is executed
AND ZFS is installed in the VM
THEN zfs and zpool commands are available
AND a testpool can be created from a loopback file
```

### FI2: Test pool persists across VM restarts

```gherkin
GIVEN Colima VM with testpool created
WHEN VM is stopped and restarted
THEN testpool can be re-imported
AND previous test data is preserved (if not cleaned up)
```

### FI3: Multiple test datasets can be created concurrently

```gherkin
GIVEN testpool exists
WHEN multiple pytest sessions create datasets simultaneously
THEN each session gets isolated datasets (unique names)
AND no conflicts occur between parallel test runs
```

## Capability Contribution

This feature provides the foundational VM environment that enables real ZFS operations. Features 54 (pytest fixtures) and 76 (mock rclone) depend on this environment being available.
