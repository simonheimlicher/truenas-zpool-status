# Push ZFS Snapshots to Dropbox for TrueNAS SCALE

A Python script that creates recursive ZFS snapshots, clones the entire dataset tree to ensure consistent traversal of nested datasets, pushes to cloud storage via rclone, and cleans up.

## Why This Script?

TrueNAS SCALE's built-in Cloud Sync Tasks fail on datasets with nested child datasets because:

1. Files change during push (the original problem)
2. Even with snapshots, traversing `.zfs/snapshot/<snap>/` still shows **live** child dataset mountpoints, not their snapshot contents

This script solves both problems by creating a **clone tree** from the recursive snapshot. The clone tree provides a truly immutable, consistent view of the entire dataset hierarchy.

## Features

- **Consistent backups**: Clones the entire snapshot tree, ensuring all nested datasets are captured at the same point in time
- **Version retention**: Optionally keeps N previous versions on the remote (via `--keep-versions`)
- **Concurrent run protection**: File-based locking prevents overlapping runs
- **Cron-friendly**: Silent on success, actionable errors on failure
- **Best-effort cleanup**: Attempts to clean up snapshots and clones on failure; exits with code 2 if cleanup fails after successful sync

## Requirements

- TrueNAS SCALE 25.10.1+ (Python 3.11+, rclone pre-installed)
- rclone configured with your cloud provider

## Setup

### 1. Create a dataset for rclone configuration

```bash
# Create a dataset on your pool (adjust pool name as needed)
zfs create apps/rclone
mkdir -p /mnt/apps/rclone
```

### 2. Configure rclone for Dropbox

Since TrueNAS SCALE doesn't have a web browser, use headless authentication:

**On your local machine (with a browser):**

```bash
# Install rclone locally if needed, then:
rclone authorize "dropbox"
```

This opens a browser for OAuth. After authorizing, you'll get a token like:

```json
{"access_token":"...","token_type":"bearer","expiry":"..."}
```

**On TrueNAS SCALE:**

```bash
rclone config --config /mnt/system/admin/dropbox-push/rclone.conf

# Follow prompts:
# n) New remote
# name> dropbox
# Storage> dropbox
# client_id> (leave blank, press Enter)
# client_secret> (leave blank, press Enter)
# Edit advanced config? n
# Use web browser to authenticate? n
# Paste the token from your local machine
# y) Yes this is OK
```

### 3. Verify rclone works

```bash
rclone --config /mnt/system/admin/dropbox-push/rclone.conf lsd dropbox:
```

### 4. Install the script

```bash
cp dropbox-push.py /mnt/system/admin/dropbox-push/dropbox-push.py
chmod +x /mnt/system/admin/dropbox-push/dropbox-push.py
```

## Usage

```
usage: dropbox-push.py [-h] [-n] [-v] [--debug] [--transfers N]
                         [--keep-versions N] [--keep-snapshot] [--keep-clone]
                         --rclone-config PATH
                         dataset destination

positional arguments:
  dataset               Source ZFS dataset (e.g., 'apps/config')
  destination           rclone destination (e.g., 'dropbox:TrueNAS-Backup/apps-config')

options:
  -n, --dry-run         Perform a trial run (note: still creates/destroys local snapshots and clones)
  -v, --verbose         Enable verbose output
  --debug               Enable debug output (implies --verbose)
  --transfers N         Number of file transfers in parallel (default: 16)
  --keep-versions N     Keep N previous versions in .versions/ subdirectory (default: 0)
  --keep-snapshot       Keep the snapshot after sync (for debugging)
  --keep-clone          Keep the clone tree after sync (for debugging)
  --rclone-config PATH  Path to rclone config file (required)
```

### Examples

```bash
# Basic sync
python3 dropbox-push.py apps/config dropbox:TrueNAS-Backup/apps-config \
    --rclone-config /mnt/system/admin/dropbox-push/rclone.conf

# Dry run with verbose output
python3 dropbox-push.py apps/config dropbox:TrueNAS-Backup/apps-config \
    --rclone-config /mnt/system/admin/dropbox-push/rclone.conf --dry-run -v

# Keep 3 previous versions on remote
python3 dropbox-push.py apps/config dropbox:TrueNAS-Backup/apps-config \
    --rclone-config /mnt/system/admin/dropbox-push/rclone.conf --keep-versions 3

# Debug mode with clone preserved for inspection
python3 dropbox-push.py apps/data dropbox:Backup/data \
    --rclone-config /mnt/system/admin/dropbox-push/rclone.conf --debug --keep-clone
```

## Version Retention

When `--keep-versions N` is specified:

- The main destination (e.g., `dropbox:Backup/apps-config`) always contains a **pristine copy** of the most recent sync
- Files that are modified or deleted are moved to `.versions/<timestamp>/` subdirectory
- After sync, old version directories beyond N are automatically deleted

**Remote structure with versioning:**

```
dropbox:Backup/apps-config/
├── audiobookshelf/
│   └── config/
├── plex-current/
│   └── config/
├── ...
└── .versions/
    ├── 2025-01-15T03-15-00Z/   # Older version
    │   └── (changed/deleted files)
    └── 20250116T031500Z/   # More recent version
        └── (changed/deleted files)
```

## How It Works

1. **Acquires lock** to prevent concurrent runs on the same dataset
2. **Validates** the ZFS dataset, rclone config, and remote
3. **Enumerates** all datasets under the root (handles nested child datasets)
4. **Creates recursive snapshot** (`apps/config@dropboxpush-2025-01-15T03-15-00Z`)
5. **Creates clone tree** from snapshots:
   - `apps/config.dropboxpush` (clone of `apps/config@dropboxpush-...`)
   - `apps/config.dropboxpush/audiobookshelf` (clone of `apps/config/audiobookshelf@dropboxpush-...`)
   - etc.
6. **pushes from clone mountpoint** via rclone (with optional `--backup-dir` for versioning)
7. **Cleans up old versions** if `--keep-versions` is set
8. **Destroys clone tree** and **snapshots**

## Setting up Cron Jobs

In TrueNAS SCALE UI: **System Settings → Advanced → Cron Jobs → Add**

| Field | Value |
|-------|-------|
| Description | Cloud Sync: apps/config to Dropbox |
| Command | `/usr/bin/python3 /mnt/system/admin/dropbox-push/dropbox-push.py apps/config dropbox:TrueNAS-Backup/apps-config --rclone-config /mnt/system/admin/dropbox-push/rclone.conf` |
| Run As User | root |
| Schedule | Custom: `0 3 * * *` (3:00 AM daily) |
| Hide Standard Output | ✓ (checked) |
| Hide Standard Error | ✗ (unchecked - you want to see errors) |

For multiple datasets, create separate cron jobs with staggered times:

```bash
# apps/config at 3:00 AM
0 3 * * * /usr/bin/python3 /mnt/system/admin/dropbox-push/dropbox-push.py apps/config dropbox:TrueNAS-Backup/apps-config --rclone-config /mnt/system/admin/dropbox-push/rclone.conf

# apps/data at 4:00 AM
0 4 * * * /usr/bin/python3 /mnt/system/admin/dropbox-push/dropbox-push.py apps/data dropbox:TrueNAS-Backup/apps-data --rclone-config /mnt/system/admin/dropbox-push/rclone.conf --keep-versions 3
```

## Behavior

| Scenario | Output |
|----------|--------|
| Success (no flags) | Silent (exit 0) |
| Success with `-v` | Progress info to stderr |
| Sync succeeded, cleanup failed | Error message to stderr (exit 2) |
| Error (any mode) | Error message to stderr (exit 1) |
| Concurrent run attempt | Error: "Another sync is already running" (exit 1) |

## Troubleshooting

### "Another sync is already running for this dataset"

A previous run may have crashed without releasing the lock. Lock files are named with a hash suffix for uniqueness:

```bash
# List lock files to find the correct one
ls /run/dropbox-push.*.lock

# Remove the stale lock (example for apps/config dataset)
rm /run/dropbox-push.apps_config-*.lock
```

### "rclone config not found"

Create the config file:

```bash
rclone config --config /mnt/system/admin/dropbox-push/rclone.conf
```

### "Remote 'dropbox' not found"

List available remotes:

```bash
rclone --config /mnt/system/admin/dropbox-push/rclone.conf listremotes
```

### "Dataset does not exist"

Verify the dataset name:

```bash
zfs list -r apps
```

### Token expired / auth error

Re-authorize on your local machine and update the token:

```bash
# On local machine with browser:
rclone authorize "dropbox"

# Then on TrueNAS, edit the config:
rclone config --config /mnt/system/admin/dropbox-push/rclone.conf
# Choose: e) Edit existing remote -> dropbox -> update token
```

### Leftover clones or snapshots

If `--keep-clone` or `--keep-snapshot` was used, or cleanup failed:

```bash
# List clones
zfs list | grep .dropboxpush

# Destroy clone tree
zfs destroy -r apps/config.dropboxpush

# List snapshots
zfs list -t snapshot | grep dropboxpush

# Destroy snapshots
zfs destroy -r apps/config@dropboxpush-2025-01-15T03-15-00Z
```

## Important Notes

### This is file-level backup, not ZFS replication

Dropbox will not preserve:

- ZFS properties
- ACLs and extended attributes
- Dataset boundaries
- File ownership (may become root on restore)

This is fine if your goal is "good enough restore by copying files back", but it's not ZFS replication. For true ZFS backup, use `zfs send/receive` to another ZFS system.

### Sync is destructive on the remote

`rclone sync` mirrors the source to destination. Files deleted locally **will be deleted on Dropbox** (unless `--keep-versions` moves them to `.versions/` first).

### Dry-run still creates local snapshots and clones

The `--dry-run` flag only affects the rclone sync and version cleanup. ZFS snapshots and clones are still created and destroyed to allow rclone to see the data structure.

## License

MIT
