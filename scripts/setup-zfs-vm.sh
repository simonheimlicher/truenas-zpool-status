#!/bin/bash
# Install ZFS in the Colima VM
#
# Prerequisites:
#   - Colima VM started with: ./scripts/start-test-vm.sh
#
# Usage:
#   ./scripts/setup-zfs-vm.sh

set -e

COLIMA_PROFILE="zfs-test"

echo "Installing ZFS in Colima VM..."
echo ""

# Check if VM is running
if ! colima status --profile "$COLIMA_PROFILE" 2>&1 | grep -qi "is running"; then
    echo "Error: Colima VM not running. Start it first with:"
    echo "  ./scripts/start-test-vm.sh"
    exit 1
fi

# Install ZFS
colima ssh --profile "$COLIMA_PROFILE" -- bash -c '
    set -e

    echo "Updating apt..."
    sudo apt-get update -qq

    echo "Installing ZFS utilities..."
    sudo apt-get install -y -qq zfsutils-linux

    echo ""
    echo "Verifying ZFS installation..."
    zfs version

    echo ""
    echo "Checking ZFS kernel modules..."
    if zpool list >/dev/null 2>&1; then
        echo "ZFS kernel modules loaded successfully."
    else
        echo "Loading ZFS kernel modules..."
        sudo modprobe zfs
        zpool list >/dev/null 2>&1 && echo "ZFS ready."
    fi
'

echo ""
echo "ZFS installed. Next step: Create test pool with:"
echo "  ./scripts/create-test-pool.sh"
