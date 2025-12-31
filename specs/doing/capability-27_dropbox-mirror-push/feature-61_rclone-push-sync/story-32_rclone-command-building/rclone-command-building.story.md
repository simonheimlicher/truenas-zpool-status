# Story: rclone Command Building

## Observable Outcome

Pure functions build rclone commands with correct options, parse rclone output, and filter by verbosity level. No I/O required - all Level 1 testable.

## Functional Requirements

### FR1: Build rclone sync command

```gherkin
GIVEN source path "/clone/data"
AND destination "dropbox:backup"
AND tpslimit 12
WHEN build_rclone_command called
THEN command includes:
  | flag          | value              |
  | sync          | -                  |
  | --links       | -                  |
  | --tpslimit    | 12                 |
  | --checksum    | -                  |
  | source        | /clone/data        |
  | destination   | dropbox:backup     |
```

### FR2: Build command with version backup

```gherkin
GIVEN keep_versions > 0
AND timestamp "2025-01-15T03-15-00Z"
WHEN build_rclone_command called
THEN command includes --backup-dir dropbox:backup/.versions/2025-01-15T03-15-00Z
```

### FR3: Parse rclone error output

```gherkin
GIVEN rclone stderr with "ERROR : file.txt: Failed to copy"
WHEN parse_rclone_error called
THEN returns structured error with:
  | field    | value           |
  | category | transfer_error  |
  | file     | file.txt        |
  | message  | Failed to copy  |

GIVEN rclone stderr with "too_many_write_operations"
WHEN parse_rclone_error called
THEN returns error with category = rate_limit
```

### FR4: Filter output by verbosity

```gherkin
GIVEN rclone output lines:
  | line                                    |
  | "Transferred: 100 MiB"                  |
  | "Copied: photo.jpg"                     |
  | "ERROR: auth failed"                    |
WHEN filter_rclone_output(lines, verbosity=0)
THEN only "ERROR: auth failed" returned

WHEN filter_rclone_output(lines, verbosity=1)
THEN "Transferred: 100 MiB" and "ERROR: auth failed" returned

WHEN filter_rclone_output(lines, verbosity=2)
THEN all lines returned
```

## Testing Level

**Level 1 (Unit)** - Pure functions, no external dependencies. Per ADR-001.

## Implementation Notes

- Extract from dropbox-push.py `run_rclone_sync` command building logic
- Use dependency injection for config values
- No subprocess calls in these functions
