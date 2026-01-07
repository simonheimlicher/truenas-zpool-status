# cloud-mirror

Mirror ZFS datasets to/from cloud storage (Dropbox) with snapshot-based consistency for TrueNAS SCALE.

**Mirror** means make the destination exactly match the source - files present only at the destination are deleted.

## Why This Tool?

TrueNAS SCALE's built-in Cloud Sync Tasks fail on datasets with nested child datasets because:

1. **Files change during operations** - the original problem
2. **Snapshots don't help** - traversing `.zfs/snapshot/<snap>/` still shows **live** child dataset mountpoints, not their snapshot contents

**cloud-mirror** solves both problems by creating a **clone tree** from recursive snapshots. The clone tree provides a truly immutable, consistent view of the entire dataset hierarchy.

## Features

- **Bidirectional mirroring**: Mirror to cloud (ZFS → remote) or from cloud (remote → ZFS)
- **Auto-direction detection**: `cloud-mirror pool/data dropbox:backup` mirrors to cloud; reverse args mirrors from cloud
- **Consistent backups**: Clones the entire snapshot tree for nested datasets
- **Version retention**: Optionally keep N previous versions on remote (`--keep-versions`)
- **Pre-mirror snapshots**: Create rollback points before mirroring from cloud (configurable)
- **Concurrent run protection**: Pool-level locking prevents overlapping operations
- **Cron-friendly**: Silent on success, actionable errors on failure

## Architecture

```
cloud_mirror/
├── __init__.py
├── cli.py          # Argument parsing
├── main.py         # Entry point, direction detection, dispatch
├── direction.py    # Auto-detect direction from arguments
├── push.py         # Mirror to cloud orchestrator (ZFS → remote)
├── pull.py         # Mirror from cloud orchestrator (remote → ZFS)
├── zfs.py          # ZFS operations (snapshots, clones, datasets)
└── rclone.py       # rclone wrapper (mirror operations, version backup)
```

### Direction Detection

Direction is auto-detected from argument format:

| First Arg        | Second Arg       | Direction                              |
| ---------------- | ---------------- | -------------------------------------- |
| `pool/data`      | `dropbox:backup` | **Mirror to cloud** (local → remote)   |
| `dropbox:backup` | `pool/data`      | **Mirror from cloud** (remote → local) |

Detection rule: rclone remotes contain `:` before any `/`; ZFS datasets have `/` before any `:` (e.g., `tank/vm:disk0`).

## How It Works

### Mirror to Cloud Workflow

1. **Acquire lock** - prevents concurrent operations on the same pool
2. **Validate** - check dataset exists, rclone config valid, remote accessible
3. **Enumerate datasets** - list all nested child datasets recursively
4. **Create recursive snapshot** - `pool/data@cloudmirror-2025-01-06T12-00-00Z`
5. **Create clone tree** - clone each snapshot to a parallel tree structure
6. **Mirror via rclone** - make remote exactly match clone mountpoint
7. **Cleanup versions** - delete old `.versions/` if `--keep-versions` set
8. **Destroy clones** - remove temporary clone tree
9. **Destroy snapshot** - remove snapshot

### Mirror from Cloud Workflow

1. **Acquire lock** - prevents concurrent operations
2. **Create pre-mirror snapshot** - `pool/data@cloudmirror-pre-2025-01-06T12-00-00Z` (rollback point)
3. **Mirror via rclone** - make local dataset exactly match remote
4. **Cleanup** - optionally keep pre-mirror snapshot for rollback

### Clone Tree Approach

Why clones instead of traversing `.zfs/snapshot/`?

```
# Problem: .zfs/snapshot shows LIVE child mountpoints
ls /pool/data/.zfs/snapshot/snap1/child/
# Shows current /pool/data/child content, NOT the snapshot!

# Solution: Clone each snapshot to get immutable view
zfs clone pool/data@snap1 pool/data.cloudpush
zfs clone pool/data/child@snap1 pool/data.cloudpush/child
# Now /pool/data.cloudpush/child shows actual snapshot content
```

## Testing

The project includes 298 tests across multiple levels, designed to run on macOS development machines while targeting TrueNAS SCALE production.

### Test Infrastructure

```
tests/
├── conftest.py              # Fixtures for ZFS, rclone, Dropbox
├── environment/             # Environment verification tests
├── fixtures/                # Fixture tests
├── unit/                    # Fast tests, no ZFS needed
│   ├── cli/                 # Argument parsing
│   ├── direction/           # Direction detection
│   ├── push/                # Push orchestrator logic
│   ├── pull/                # Pull operations
│   └── rclone/              # rclone command building
└── integration/             # Require ZFS or network
    ├── zfs/                 # Snapshot/clone operations
    ├── rclone/              # Mirror operations
    ├── push/                # Full mirror-to-cloud workflow
    └── dropbox/             # Real Dropbox (Level 3)
```

### Test Levels

| Level               | Marker                           | Requires           | Speed  |
| ------------------- | -------------------------------- | ------------------ | ------ |
| Unit                | (none)                           | Nothing            | Fast   |
| VM Integration      | `@pytest.mark.vm_required`       | Colima VM with ZFS | Medium |
| Network Integration | `@pytest.mark.internet_required` | Dropbox token      | Slow   |

### Development Environment (macOS)

Since ZFS doesn't run natively on macOS, tests use a **Colima VM** with ZFS installed:

```bash
# Start Colima VM for ZFS testing
./scripts/start-test-vm.sh

# Install ZFS in the VM
./scripts/setup-zfs-vm.sh

# Create test pool
./scripts/create-test-pool.sh

# Run all tests
uv run --extra dev pytest tests/ -v

# Run only unit tests (no VM needed)
uv run --extra dev pytest tests/ -v -m "not vm_required"

# Run VM tests
uv run --extra dev pytest tests/ -v -m "vm_required"

# Run Dropbox tests (requires DROPBOX_TEST_TOKEN in .env)
uv run --extra dev pytest tests/ -v -m "internet_required"
```

### Testing Philosophy

- **Real infrastructure**: Tests use actual ZFS (in VM) and rclone, not mocks
- **Dependency injection**: Orchestrators accept injected dependencies for testability
- **Graduated tests**: Tests start in `specs/` during development, graduate to `tests/` when complete
- **Three-tier Dropbox testing**: Mock → VM-local → Real Dropbox

## Requirements

- **TrueNAS SCALE 25.10** (Goldeye) or later
- **Python 3.11+** (included in TrueNAS SCALE)
- **rclone** (pre-installed on TrueNAS SCALE)
- **Configured rclone remote** (e.g., Dropbox)

## Installation on TrueNAS SCALE 25.10

### 1. Create a dataset for the script and config

```bash
# Create dataset (adjust pool name as needed)
zfs create apps/cloud-mirror

# Create directory structure
mkdir -p /mnt/apps/cloud-mirror
```

### 2. Copy the cloud-mirror package

```bash
# Copy the entire cloud_mirror package
cp -r cloud_mirror/ /mnt/apps/cloud-mirror/

# Or copy just the essential files
cp cloud_mirror/*.py /mnt/apps/cloud-mirror/cloud_mirror/
```

### 3. Configure rclone for Dropbox (headless)

Since TrueNAS SCALE doesn't have a browser, use headless authentication:

**On your local machine (with browser):**

```bash
rclone authorize "dropbox"
# This opens browser for OAuth, then outputs a token
```

**On TrueNAS SCALE:**

```bash
rclone config --config /mnt/apps/cloud-mirror/rclone.conf

# Follow prompts:
# n) New remote
# name> dropbox
# Storage> dropbox
# client_id> (leave blank)
# client_secret> (leave blank)
# Edit advanced config? n
# Use web browser? n
# Paste the token from local machine
# y) Yes this is OK
```

### 4. Verify rclone works

```bash
rclone --config /mnt/apps/cloud-mirror/rclone.conf lsd dropbox:
```

## Usage

Direction is auto-detected from argument order:

```bash
cloud-mirror <source> <destination> [options]

# Mirror to cloud (dataset first)
cloud-mirror apps/config dropbox:TrueNAS-Backup/apps-config \
    --config /mnt/apps/cloud-mirror/rclone.conf

# Mirror from cloud (remote first)
cloud-mirror dropbox:Backup/data apps/data \
    --config /mnt/apps/cloud-mirror/rclone.conf

# With version retention (when mirroring to cloud)
cloud-mirror apps/data dropbox:Backup/data \
    --config /mnt/apps/cloud-mirror/rclone.conf \
    --keep-versions 3

# Dry run
cloud-mirror apps/config dropbox:Backup \
    --config /mnt/apps/cloud-mirror/rclone.conf \
    --dry-run -v
```

### Options

| Option                | Default | Description                                         |
| --------------------- | ------- | --------------------------------------------------- |
| `--config PATH`       | None    | Path to rclone config file                          |
| `--transfers N`       | 64      | Parallel file transfers                             |
| `--tpslimit N`        | 12      | Transactions per second limit                       |
| `--dry-run`           | False   | Trial run, no changes                               |
| `-v, -vv, -vvv`       | 0       | Verbosity level                                     |
| `--keep-versions N`   | 0       | Keep N old versions (when mirroring to cloud)       |
| `--keep-snapshot`     | False   | Keep snapshot after mirror (when to cloud)          |
| `--keep-clone`        | False   | Keep clone tree after mirror (when to cloud)        |
| `--keep-pre-snapshot` | False   | Keep pre-mirror snapshot (when from cloud)          |
| `--no-pre-snapshot`   | False   | Skip creating pre-mirror snapshot (when from cloud) |

## Cron Job Setup for TrueNAS SCALE 25.10

### Via Web UI

Navigate to **System > Advanced Settings > Cron Jobs > Add**

| Field                    | Value                                                                                                     |
| ------------------------ | --------------------------------------------------------------------------------------------------------- |
| **Description**          | Cloud Mirror: apps/config to Dropbox                                                                      |
| **Command**              | `cloud-mirror apps/config dropbox:TrueNAS-Backup/apps-config --config /mnt/apps/cloud-mirror/rclone.conf` |
| **Run As User**          | root                                                                                                      |
| **Schedule**             | Custom: `0 3 * * *` (3:00 AM daily)                                                                       |
| **Hide Standard Output** | Checked                                                                                                   |
| **Hide Standard Error**  | Unchecked (receive error emails)                                                                          |
| **Enabled**              | Checked                                                                                                   |

### Via CLI

TrueNAS SCALE provides a CLI that persists across reboots:

```bash
# Create cron job via CLI
midclt call task.cron_job.create '{
  "description": "Cloud Mirror: apps/config to Dropbox",
  "command": "cloud-mirror apps/config dropbox:TrueNAS-Backup/apps-config --config /mnt/apps/cloud-mirror/rclone.conf",
  "user": "root",
  "schedule": {
    "minute": "0",
    "hour": "3",
    "dom": "*",
    "month": "*",
    "dow": "*"
  },
  "enabled": true,
  "stdout": false,
  "stderr": true
}'
```

### Multiple Datasets with Staggered Times

Create separate cron jobs for each dataset:

| Dataset      | Schedule    | Time    |
| ------------ | ----------- | ------- |
| apps/config  | `0 3 * * *` | 3:00 AM |
| apps/data    | `0 4 * * *` | 4:00 AM |
| media/photos | `0 5 * * *` | 5:00 AM |

### TrueNAS SCALE 25.10 Important Notes

1. **Root account RBAC**: Removing the `FULL_ADMIN` role from root can cause cron jobs to fail. Keep root with full admin privileges or use the "Disable Password" option instead.

2. **Cron format**: TrueNAS uses standard cron format with five fields: `minute hour day-of-month month day-of-week`

3. **Output handling**:
   - Check "Hide Standard Output" to suppress success messages
   - Leave "Hide Standard Error" unchecked to receive error notifications

## Troubleshooting

### "Could not acquire lock for pool"

Another operation is running, or a previous run crashed:

```bash
# Find lock files
ls /var/run/cloud-mirror/

# Remove stale lock (if you're sure nothing is running)
rm /var/run/cloud-mirror/testpool.lock
```

### Leftover clones or snapshots

If cleanup failed or `--keep-clone` was used:

```bash
# List clones
zfs list | grep cloudpush

# Destroy clone tree
zfs destroy -r pool/data.cloudpush

# List snapshots
zfs list -t snapshot | grep cloudpush

# Destroy snapshots
zfs destroy -r pool/data@cloudpush-2025-01-06T12-00-00Z
```

### Token expired / auth error

Re-authorize on a machine with a browser:

```bash
# On local machine
rclone authorize "dropbox"

# On TrueNAS, update config
rclone config --config /mnt/apps/cloud-mirror/rclone.conf
# e) Edit existing remote -> dropbox -> update token
```

### Cron job not running (TrueNAS 25.10)

Verify root has proper RBAC roles:

1. Go to **Credentials > Local Users**
2. Edit the root user
3. Ensure `FULL_ADMIN` role is assigned
4. If you want to disable root UI access, use "Disable Password" instead of removing roles

## Important Notes

### This is file-level backup, not ZFS replication

Dropbox will not preserve:

- ZFS properties
- ACLs and extended attributes
- Dataset boundaries
- File ownership (may become root on restore)

For true ZFS backup, use `zfs send/receive` to another ZFS system.

### Mirroring is destructive

Mirroring makes the destination exactly match the source. Files present only at the destination **will be deleted** (unless `--keep-versions` moves them to `.versions/` first when mirroring to cloud).

### Dry-run still creates local snapshots

The `--dry-run` flag only affects rclone operations. ZFS snapshots and clones are still created/destroyed to allow rclone to see the data structure.

## License

MIT

---

**Sources:**

- [Managing Cron Jobs - TrueNAS Documentation](https://www.truenas.com/docs/scale/scaletutorials/systemsettings/advanced/managecronjobsscale/)
- [TrueNAS SCALE 25.10 Version Notes](https://www.truenas.com/docs/scale/25.10/gettingstarted/versionnotes/)
