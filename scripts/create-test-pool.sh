#!/bin/bash
# Create a test ZFS pool from a loopback file in the Colima VM
#
# Prerequisites:
#   - Colima VM started with: ./scripts/start-test-vm.sh
#   - ZFS installed with: ./scripts/setup-zfs-vm.sh
#
# Usage:
#   ./scripts/create-test-pool.sh           # Create pool
#   ./scripts/create-test-pool.sh --destroy # Destroy pool

set -e

COLIMA_PROFILE="zfs-test"
POOL_NAME="testpool"
POOL_FILE="/zfs-test/testpool.img"
POOL_SIZE="512M"

# Check if VM is running
if ! colima status --profile "$COLIMA_PROFILE" 2>&1 | grep -qi "is running"; then
    echo "Error: Colima VM not running. Start it first with:"
    echo "  ./scripts/start-test-vm.sh"
    exit 1
fi

case "${1:-create}" in
    --destroy)
        echo "Destroying test pool..."
        colima ssh --profile "$COLIMA_PROFILE" -- bash -c "
            set -e
            if zpool list $POOL_NAME >/dev/null 2>&1; then
                sudo zpool destroy -f $POOL_NAME
                echo 'Pool destroyed.'
            else
                echo 'Pool does not exist.'
            fi
            if [ -f $POOL_FILE ]; then
                sudo rm $POOL_FILE
                echo 'Pool file removed.'
            fi
        "
        ;;
    create|*)
        echo "Creating test pool '$POOL_NAME'..."
        echo ""

        colima ssh --profile "$COLIMA_PROFILE" -- bash -c "
            set -e

            # Check if pool already exists
            if zpool list $POOL_NAME >/dev/null 2>&1; then
                echo 'Pool already exists:'
                zpool status $POOL_NAME
                exit 0
            fi

            # Check if pool file exists but pool isn't imported
            if [ -f $POOL_FILE ]; then
                echo 'Pool file exists, attempting import...'
                if sudo zpool import -d /zfs-test $POOL_NAME 2>/dev/null; then
                    echo 'Pool imported successfully:'
                    zpool status $POOL_NAME
                    exit 0
                else
                    echo 'Import failed, recreating pool...'
                    sudo rm -f $POOL_FILE
                fi
            fi

            # Create directory for pool file
            sudo mkdir -p /zfs-test

            # Create sparse file for pool
            echo 'Creating $POOL_SIZE sparse file...'
            sudo truncate -s $POOL_SIZE $POOL_FILE

            # Create pool
            echo 'Creating ZFS pool...'
            sudo zpool create -f $POOL_NAME $POOL_FILE

            echo ''
            echo 'Pool created successfully:'
            zpool status $POOL_NAME
            echo ''
            zfs list $POOL_NAME
        "

        echo ""
        echo "Test pool ready. You can now run tests with:"
        echo "  colima ssh --profile $COLIMA_PROFILE"
        echo "  cd /path/to/cloud-mirror && pytest tests/ -m zfs -v"
        ;;
esac
