# Story: ZFS Installation

## Functional Requirements

### FR1: ZFS tools installed in Colima VM

```gherkin
GIVEN Colima VM running with Ubuntu
WHEN apt-get install zfsutils-linux executed
THEN zfs command is available
AND zpool command is available
AND ZFS kernel modules are loaded
```

#### Files created/modified

1. `scripts/setup-zfs-vm.sh` [new]: Script to install ZFS in Colima VM

**Test Validation:**

1. Integration test: `specs/doing/capability-10_docker-test-environment/feature-32_colima-zfs-environment/story-54_zfs-installation/tests/test_zfs_installation.py`

### FR2: ZFS kernel modules loaded

```gherkin
GIVEN ZFS tools installed
WHEN zpool list executed
THEN command succeeds (exit code 0)
AND no "kernel module not loaded" error
```

### FR3: ZFS persists across VM restarts

```gherkin
GIVEN ZFS installed in Colima VM
WHEN VM stopped and restarted
THEN ZFS tools still available
AND kernel modules still loadable
```

## Quality Requirements

### QR1: Minimal installation

**Requirement:** Only install what's needed for testing
**Target:** zfsutils-linux package only, no extras
**Validation:** Package list verification

### QR2: No manual intervention

**Requirement:** Installation should be scriptable
**Target:** Single command installs everything
**Validation:** Script runs without prompts
