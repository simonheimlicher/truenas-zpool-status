# Feature: Mock rclone Remote

## Observable Outcome

Tests can use rclone sync operations without connecting to actual Dropbox. A local filesystem backend acts as the "remote", enabling full sync testing without network dependencies.

## Feature Integration Tests

### FI1: Local backend configured as test remote

```gherkin
GIVEN rclone-test.conf with [testremote] type=local
WHEN rclone --config rclone-test.conf listremotes
THEN testremote: is listed as available remote
```

### FI2: Sync to local remote works like real remote

```gherkin
GIVEN source directory with files
AND test_remote fixture providing local remote path
WHEN rclone sync source/ testremote:destination/
THEN files appear in the local destination directory
AND directory structure is preserved
```

### FI3: Symlinks handled correctly

```gherkin
GIVEN source directory with symlinks
WHEN rclone sync with --links option
THEN symlinks become .rclonelink files on remote
AND syncing back restores symlinks
```

### FI4: Test remote fixture provides isolated paths

```gherkin
GIVEN multiple tests using test_remote fixture
WHEN tests run in parallel
THEN each test gets unique remote path (via pytest tmp_path)
AND no conflicts between test data
```

## Capability Contribution

This feature eliminates the need for real Dropbox credentials during testing. Combined with ZFS fixtures, it enables complete end-to-end testing of sync operations locally.
