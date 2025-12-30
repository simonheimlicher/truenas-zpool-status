"""
Environment verification tests.

These tests verify the Colima VM, ZFS installation, and test pool are ready.
They serve as regression protection for the test infrastructure.

Run these first to verify the environment is healthy:
    uv run --extra dev pytest tests/environment/ -v

Tests are ordered from trivial to complex within each file:
1. test_colima.py - Colima installed and VM accessible
2. test_zfs_in_vm.py - ZFS installed and kernel modules loaded in VM
3. test_pool.py - testpool exists and healthy, dataset operations work
"""
