# ADR: Colima with Ubuntu for ZFS Testing on macOS

## Problem

We need to run ZFS integration tests on macOS development machines. ZFS requires kernel modules that are not available in Docker Desktop's LinuxKit VM. How do we provide a working ZFS environment for local testing?

## Options Considered

### Option 1: Docker Desktop with ZFS (Not Feasible)

Docker Desktop on macOS uses a LinuxKit-based VM that does not include ZFS kernel modules. ZFS cannot be installed in containers without kernel support from the host VM.

### Option 2: Colima with Ubuntu VM

Colima is a container runtime for macOS that uses Lima VMs. It can run Ubuntu VMs instead of the default Alpine, and Ubuntu supports ZFS via `zfsutils-linux`. Tests run directly in the Colima VM with real ZFS.

### Option 3: Dedicated Linux VM (UTM/Parallels)

Run a full Ubuntu VM with ZFS installed. Provides complete control but requires separate VM management outside the Docker workflow.

### Option 4: Remote Testing Only

Only run ZFS tests on actual TrueNAS or a remote Linux server. Local development uses mocks only.

## Decision

**We will use Colima with Ubuntu for ZFS testing.**

## Rationale

Colima provides the best balance of:

- **Real ZFS operations**: Ubuntu in Colima has full ZFS kernel module support
- **Docker compatibility**: Colima is a drop-in Docker replacement; `docker` and `docker compose` commands work unchanged
- **Local development**: Tests run on the developer's Mac without remote infrastructure
- **Simplicity**: Single `colima start` command to get a working environment

The key insight is that we run tests *inside* the Colima VM (via `colima ssh` or Lima directly), not in Docker containers. This gives us native ZFS access.

## Trade-offs Accepted

- **Not pure Docker**: ZFS tests run in the VM, not in containers. This is acceptable because ZFS requires kernel modules.
- **macOS-specific**: This solution targets macOS developers. Linux developers can run tests natively.
- **VM overhead**: Colima adds VM overhead, but this is acceptable for integration tests.

## Constraints

- ZFS integration tests must be marked with `@pytest.mark.zfs` so they can be skipped when ZFS is unavailable
- Unit tests (no ZFS) should run in plain Docker containers for speed
- The Colima VM must create a test ZFS pool on startup using a loopback file
- Tests must not depend on specific pool names; use fixtures that create isolated datasets
