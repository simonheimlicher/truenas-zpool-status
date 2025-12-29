# Feature: Direction Detection

## Observable Outcome

The sync direction (PUSH or PULL) is automatically detected based on argument order. rclone remotes (containing colon) are distinguished from ZFS datasets.

## Feature Integration Tests

### FI1: Push direction detected (dataset first)

```gherkin
GIVEN arguments: "testpool/data" "testremote:backup"
WHEN detect_direction called
THEN returns SyncEndpoints with:
  | field       | value              |
  | direction   | PUSH               |
  | zfs_dataset | testpool/data      |
  | remote      | testremote:backup  |
```

### FI2: Pull direction detected (remote first)

```gherkin
GIVEN arguments: "testremote:backup" "testpool/data"
WHEN detect_direction called
THEN returns SyncEndpoints with:
  | field       | value              |
  | direction   | PULL               |
  | zfs_dataset | testpool/data      |
  | remote      | testremote:backup  |
```

### FI3: ZFS dataset with colon recognized correctly

```gherkin
GIVEN argument: "tank/vm:disk0"
WHEN is_rclone_remote called
THEN returns False
BECAUSE slash appears before colon (ZFS pattern)
```

### FI4: rclone remote formats recognized

```gherkin
GIVEN arguments:
  | arg               | expected  |
  | dropbox:path      | remote    |
  | remote:           | remote    |
  | my_remote:folder  | remote    |
  | s3:bucket/key     | remote    |
WHEN is_rclone_remote called
THEN returns True for all
```

### FI5: Both remotes raises error

```gherkin
GIVEN arguments: "remote1:path" "remote2:path"
WHEN detect_direction called
THEN raises DropboxSyncError
AND error message explains both appear to be remotes
```

### FI6: Neither remote raises error

```gherkin
GIVEN arguments: "pool1/data" "pool2/backup"
WHEN detect_direction called
THEN raises DropboxSyncError
AND error message explains neither appears to be a remote
```

## Capability Contribution

Direction detection enables the bidirectional nature of `cloud-mirror.py`. Without it, separate push and pull scripts would be required, complicating the user experience.
