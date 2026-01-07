# Story: Push Integration

## What Changes

Wire together CLI, direction detection, orchestrator, and locking into working cloud-mirror script.

## Functional Requirements

### FR1: CLI invokes orchestrator

```gherkin
GIVEN cloud-mirror testpool/data dropbox:backup
WHEN executed
THEN direction detected as MIRROR TO CLOUD
AND RealPushOperations created with zfs.py and rclone.py
AND PushOrchestrator runs workflow
AND exit code reflects success (0) or failure (1)
```

### FR2: Dry run mode

```gherkin
GIVEN --dry-run flag
WHEN push executes
THEN snapshot and clone created (for validation)
AND rclone runs with --dry-run (no actual transfer)
AND snapshot and clone destroyed after
```

### FR3: Verbose output

```gherkin
GIVEN -v flag
WHEN push executes
THEN progress messages shown for each step
AND rclone output filtered to level 1

GIVEN -vv flag
THEN rclone output at level 2 (file details)
```

### FR4: Error messages

```gherkin
GIVEN push fails with known error
WHEN error caught
THEN user-friendly message printed to stderr
AND suggestion for resolution included
AND exit code is 1
```

### FR5: Config file option

```gherkin
GIVEN --config /path/to/rclone.conf
WHEN push executes
THEN rclone uses specified config file
AND default is ~/.config/rclone/rclone.conf
```

## Testing Level

**Level 2 (VM)**: Full integration with real ZFS and local rclone backend.

**Level 3 (Internet)**: E2E with real Dropbox (one smoke test).

## Implementation Notes

- Main function in cloud_mirror/main.py with console script entry point
- Setup logging based on verbose level
- Wrap errors in user-friendly messages
- Return appropriate exit codes
- Support Ctrl+C gracefully (cleanup before exit)
