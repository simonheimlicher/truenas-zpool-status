# Story: Version Backup

## Observable Outcome

Modified and deleted files are preserved in a versioned backup directory. Old versions are cleaned up to maintain only the N most recent.

## Functional Requirements

### FR1: Backup changed files to versions directory

```gherkin
GIVEN remote contains file1.txt with "old content"
AND source has file1.txt with "new content"
WHEN run_rclone_sync with keep_versions=3
THEN remote file1.txt has "new content"
AND remote .versions/TIMESTAMP/file1.txt has "old content"
```

### FR2: Backup deleted files

```gherkin
GIVEN remote contains deleted.txt
AND source does NOT have deleted.txt
WHEN run_rclone_sync with keep_versions=3
THEN remote deleted.txt is removed
AND remote .versions/TIMESTAMP/deleted.txt exists
```

### FR3: Cleanup old versions

```gherkin
GIVEN remote .versions/ has 5 timestamp directories:
  | directory            |
  | 2025-01-10T00-00-00Z |
  | 2025-01-11T00-00-00Z |
  | 2025-01-12T00-00-00Z |
  | 2025-01-13T00-00-00Z |
  | 2025-01-14T00-00-00Z |
WHEN cleanup_old_versions(remote, keep_versions=3) called
THEN only 3 most recent remain:
  | directory            |
  | 2025-01-12T00-00-00Z |
  | 2025-01-13T00-00-00Z |
  | 2025-01-14T00-00-00Z |
AND oldest 2 are deleted
```

### FR4: Skip cleanup if not enough versions

```gherkin
GIVEN remote .versions/ has 2 timestamp directories
WHEN cleanup_old_versions(remote, keep_versions=3) called
THEN no directories deleted
AND function returns without error
```

## Testing Levels

- **Level 2 (VM)**: Version backup with local backend
- **Level 3 (Internet)**: Cleanup on real Dropbox (per ADR-001)

## Implementation Notes

- Uses rclone --backup-dir flag for versioning
- Cleanup uses rclone lsd to list version directories
- Cleanup uses rclone purge to delete old versions
- Timestamp format: ISO 8601 with dashes replacing colons
