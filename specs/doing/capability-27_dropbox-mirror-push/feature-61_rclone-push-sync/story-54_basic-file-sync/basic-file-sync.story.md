# Story: Basic File Sync

## Observable Outcome

Files sync from source to remote destination using rclone. Symlinks are converted to .rclonelink files. Directory structure is preserved.

## Functional Requirements

### FR1: Sync files to remote

```gherkin
GIVEN source directory with:
  | path              | content   |
  | file1.txt         | content1  |
  | subdir/file2.txt  | content2  |
AND rclone remote configured
WHEN run_rclone_sync(source, remote) called
THEN files appear on remote with correct content
AND directory structure preserved
```

### FR2: Symlinks become .rclonelink files

```gherkin
GIVEN source with:
  | path       | type    | target     |
  | target.txt | file    | -          |
  | link.txt   | symlink | target.txt |
WHEN run_rclone_sync with --links
THEN remote contains:
  | path               | content         |
  | target.txt         | (original)      |
  | link.txt.rclonelink| target.txt      |
```

### FR3: Handle sync errors gracefully

```gherkin
GIVEN invalid remote configuration
WHEN run_rclone_sync called
THEN raises RcloneError with helpful message
AND suggests fix (e.g., "rclone config reconnect")
```

## Testing Levels

- **Level 2 (VM)**: Real rclone with `type=local` backend
- **Level 3 (Internet)**: Real Dropbox (per ADR-001, MANDATORY)

## Implementation Notes

- Extract from dropbox-push.py `run_rclone_sync`
- Must support both local backend (testing) and real remotes (production)
- Use subprocess with timeout
- Capture and parse stdout/stderr
