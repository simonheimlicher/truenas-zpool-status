# Feature: Push CLI

## Observable Outcome

Command-line interface accepts push arguments and orchestrates the complete push workflow: validation, snapshot, clone, sync, cleanup.

## Feature Integration Tests

### FI1: CLI accepts dataset and remote arguments

```gherkin
GIVEN cloud-mirror.py script
WHEN executed with: cloud-mirror.py testpool/data testremote:backup
THEN args.source = "testpool/data"
AND args.destination = "testremote:backup"
AND push workflow executes
```

### FI2: Push-specific options parsed

```gherkin
GIVEN cloud-mirror.py with options:
  | option          | value |
  | --keep-versions | 3     |
  | --keep-snapshot | true  |
  | --keep-clone    | true  |
  | --transfers     | 32    |
  | --tpslimit      | 10    |
WHEN parse_args called
THEN all options available in args namespace
```

### FI3: run_push orchestrates full workflow

```gherkin
GIVEN valid dataset and remote
WHEN run_push(dataset, remote, args, logger, verbose_level) called
THEN workflow executes in order:
  1. Validate dataset exists
  2. Validate rclone config and remote
  3. List datasets recursively
  4. Create recursive snapshot
  5. Create clone tree
  6. Run rclone sync
  7. Cleanup old versions (if --keep-versions)
  8. Destroy clone tree (unless --keep-clone)
  9. Destroy snapshot (unless --keep-snapshot)
```

### FI4: Cleanup occurs even on sync failure

```gherkin
GIVEN push operation where rclone sync fails
WHEN error is caught
THEN clone tree is still destroyed (unless --keep-clone)
AND snapshot is still destroyed (unless --keep-snapshot)
AND appropriate exit code returned
```

### FI5: Lock prevents concurrent runs

```gherkin
GIVEN push operation running on testpool/data
WHEN second push attempted on same dataset
THEN second operation fails immediately
AND error message indicates lock conflict
```

### FI6: Dry run creates but doesn't sync

```gherkin
GIVEN --dry-run option
WHEN push executes
THEN snapshot and clone created (for validation)
AND rclone runs with --dry-run (no actual transfer)
AND snapshot and clone destroyed after
```

## Capability Contribution

This feature provides the user interface and workflow orchestration for push operations. It combines all other push features into a cohesive command-line tool.
