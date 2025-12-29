# Feature: Pull CLI

## Observable Outcome

Command-line interface accepts pull arguments (remote first, then dataset) and orchestrates the pull workflow. Main dispatches to run_push or run_pull based on detected direction.

## Feature Integration Tests

### FI1: CLI accepts remote and dataset arguments

```gherkin
GIVEN cloud-mirror.py script
WHEN executed with: cloud-mirror.py testremote:source testpool/target
THEN args.source = "testremote:source"
AND args.destination = "testpool/target"
AND pull workflow executes (not push)
```

### FI2: Pull-specific options parsed

```gherkin
GIVEN cloud-mirror.py with options:
  | option              | effect                           |
  | --keep-pre-snapshot | preserve pre-pull snapshot       |
  | --no-pre-snapshot   | skip creating pre-pull snapshot  |
WHEN parse_args called
THEN options available in args namespace
```

### FI3: Main dispatches by detected direction

```gherkin
GIVEN cloud-mirror.py with arguments that detect as PULL
WHEN main() executes
THEN detect_direction returns PULL
AND run_pull called (not run_push)
```

```gherkin
GIVEN cloud-mirror.py with arguments that detect as PUSH
WHEN main() executes
THEN detect_direction returns PUSH
AND run_push called (not run_pull)
```

### FI4: Warning when pulling to dataset with children

```gherkin
GIVEN target dataset testpool/parent has children:
  | dataset                  |
  | testpool/parent/child1   |
WHEN pull starts
THEN warning logged:
  "Target dataset has child datasets. Pull is flat - files will go to parent only."
AND pull continues (not blocked)
```

### FI5: Dry run works for pull

```gherkin
GIVEN --dry-run option with pull arguments
WHEN pull executes
THEN pre-pull snapshot created (for validation)
AND rclone runs with --dry-run (no actual transfer)
AND pre-pull snapshot destroyed after
```

### FI6: Exit codes consistent with push

```gherkin
GIVEN pull operation
WHEN operation succeeds
THEN exit code 0
WHEN operation fails
THEN exit code 1
WHEN sync succeeds but cleanup fails
THEN exit code 2
WHEN interrupted by Ctrl+C
THEN exit code 130
WHEN terminated by SIGTERM
THEN exit code 143
```

## Capability Contribution

This feature provides the user interface for pull operations and integrates with the existing push CLI. The unified `cloud-mirror.py` script handles both directions, simplifying the user experience.
