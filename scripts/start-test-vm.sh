#!/bin/bash
# Start Colima VM with settings optimized for ZFS testing
#
# Usage:
#   ./scripts/start-test-vm.sh          # Start VM
#   ./scripts/start-test-vm.sh --stop   # Stop VM
#   ./scripts/start-test-vm.sh --status # Check status

set -e

COLIMA_PROFILE="zfs-test"

case "${1:-start}" in
    --stop)
        echo "Stopping Colima VM..."
        colima stop --profile "$COLIMA_PROFILE" 2>/dev/null || true
        echo "VM stopped."
        ;;
    --status)
        colima status --profile "$COLIMA_PROFILE" 2>/dev/null || echo "VM not running"
        ;;
    start|*)
        echo "Starting Colima VM for ZFS testing..."
        echo "Profile: $COLIMA_PROFILE"
        echo ""

        # Check if already running
        if colima status --profile "$COLIMA_PROFILE" 2>&1 | grep -qi "is running"; then
            echo "VM already running."
            exit 0
        fi

        # Start with Ubuntu (not Alpine/LinuxKit) for ZFS support
        # Using vz (Virtualization.framework) for better performance on Apple Silicon
        colima start \
            --profile "$COLIMA_PROFILE" \
            --vm-type vz \
            --mount-type virtiofs \
            --cpu 4 \
            --memory 8 \
            --disk 60 \
            --ssh-agent

        echo ""
        echo "VM started. To access:"
        echo "  colima ssh --profile $COLIMA_PROFILE"
        echo ""
        echo "Next step: Install ZFS with:"
        echo "  ./scripts/setup-zfs-vm.sh"
        ;;
esac
