# Feature: Pull Sync Operations

## Observable Outcome

Files sync from remote to local ZFS dataset with pre-pull snapshot for rollback safety. The snapshot is preserved on failure, destroyed on success.

## Feature Integration Tests

### FI1: Pre-pull snapshot created before sync

```gherkin
GIVEN ZFS dataset testpool/target exists
WHEN create_pre_pull_snapshot(testpool/target, timestamp, logger) called
THEN snapshot testpool/target@dropboxpull-pre-TIMESTAMP exists
AND snapshot is non-recursive (single dataset only)
```

### FI2: rclone pull syncs from remote to local

```gherkin
GIVEN remote testremote:source with files
AND local mountpoint /testpool/target
WHEN run_rclone_pull called
THEN rclone sync testremote:source /testpool/target/ executed
AND --links option included (restore symlinks)
AND --exclude .versions/** included (skip remote versions)
```

### FI3: run_pull orchestrates complete workflow

```gherkin
GIVEN valid remote and dataset
WHEN run_pull(remote, dataset, args, logger, verbose_level) called
THEN workflow executes in order:
  1. Validate dataset exists and has mountpoint
  2. Validate rclone config and remote
  3. Create pre-pull snapshot
  4. Run rclone pull
  5. Destroy pre-pull snapshot (on success)
```

### FI4: Pre-pull snapshot preserved on failure

```gherkin
GIVEN pull operation starts successfully
AND pre-pull snapshot created
WHEN rclone sync fails (non-zero exit)
THEN pre-pull snapshot is NOT destroyed
AND error message includes:
  "Pre-pull snapshot preserved for rollback"
  "To rollback: zfs rollback testpool/target@dropboxpull-pre-TIMESTAMP"
```

### FI5: Pre-pull snapshot kept with --keep-pre-snapshot

```gherkin
GIVEN --keep-pre-snapshot option
WHEN pull succeeds
THEN pre-pull snapshot is NOT destroyed
AND info message indicates snapshot preserved for inspection
```

### FI6: Pre-pull snapshot skipped with --no-pre-snapshot

```gherkin
GIVEN --no-pre-snapshot option
WHEN pull executes
THEN no pre-pull snapshot created
AND warning logged about disabled rollback safety
```

## Capability Contribution

This feature performs the actual data transfer from remote to local. The pre-pull snapshot provides safety for the destructive sync operation - if anything goes wrong, the user can rollback to the previous state.
