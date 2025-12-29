# Feature: rclone Push Sync

## Observable Outcome

Files sync from clone tree to remote with rate limiting, symlink preservation, and optional version backup. rclone output is filtered by verbosity level.

## Feature Integration Tests

### FI1: Basic sync copies files to remote

```gherkin
GIVEN clone mountpoint with files:
  | path              | content   |
  | file1.txt         | content1  |
  | subdir/file2.txt  | content2  |
AND test remote configured
WHEN run_rclone_sync called
THEN files appear on remote with correct content
AND directory structure preserved
```

### FI2: Symlinks converted to .rclonelink files

```gherkin
GIVEN clone mountpoint with:
  | path       | type    | target     |
  | target.txt | file    | -          |
  | link.txt   | symlink | target.txt |
WHEN run_rclone_sync with --links
THEN remote contains:
  | path             | content    |
  | target.txt       | (original) |
  | link.txt.rclonelink | target.txt |
```

### FI3: Version backup preserves old files

```gherkin
GIVEN remote already contains file1.txt with "old content"
AND clone has file1.txt with "new content"
WHEN run_rclone_sync with --keep-versions 3
THEN remote file1.txt has "new content"
AND remote .versions/TIMESTAMP/file1.txt has "old content"
```

### FI4: Old versions cleaned up

```gherkin
GIVEN remote .versions/ has 5 timestamp directories
WHEN cleanup_old_versions called with keep_versions=3
THEN only 3 most recent version directories remain
AND oldest 2 are deleted
```

### FI5: Rate limiting applied

```gherkin
GIVEN --tpslimit 12 option
WHEN run_rclone_sync executes
THEN rclone command includes --tpslimit 12
```

### FI6: Output filtered by verbosity

```gherkin
GIVEN rclone produces verbose output
WHEN run_rclone_sync with verbose_level=0
THEN only errors and rate limit warnings shown
WHEN run_rclone_sync with verbose_level=1
THEN progress summaries shown, individual files hidden
WHEN run_rclone_sync with verbose_level=2
THEN all output shown including file transfers
```

## Capability Contribution

This feature performs the actual data transfer to the remote. It integrates with the clone tree (source) and handles Dropbox-specific concerns like rate limiting and symlink conversion.
