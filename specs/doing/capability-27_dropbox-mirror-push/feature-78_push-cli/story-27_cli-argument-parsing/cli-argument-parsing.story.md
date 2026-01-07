# Story: CLI Argument Parsing

## What Changes

Implement argument parsing for cloud-mirror using argparse with simple positional arguments (no subcommands).

## Functional Requirements

### FR1: Positional arguments for source and destination

```gherkin
GIVEN cloud-mirror script
WHEN executed with: cloud-mirror testpool/data dropbox:backup
THEN args.source = "testpool/data"
AND args.destination = "dropbox:backup"
```

### FR2: Options

```gherkin
GIVEN cloud-mirror with options:
  | option              | default |
  | --keep-versions     | 0       |
  | --keep-snapshot     | false   |
  | --keep-clone        | false   |
  | --keep-pre-snapshot | false   |
  | --no-pre-snapshot   | false   |
  | --transfers         | 64      |
  | --tpslimit          | 12      |
  | --dry-run           | false   |
  | --config            | None    |
WHEN parse_args called
THEN all options available in args namespace with defaults
```

### FR3: Verbose levels

```gherkin
GIVEN -v, -vv, or -vvv flags
WHEN parsed
THEN verbose level = 1, 2, or 3 respectively
AND default is 0
```

### FR4: Help message

```gherkin
GIVEN --help flag
WHEN executed
THEN shows usage with all options documented
AND exits with code 0
```

## Testing Level

**Level 1 (Unit)**: Pure argparse logic, no external dependencies.

## Implementation Notes

- Use argparse with simple positional arguments (no subcommands)
- Direction detection happens in main.py, not in argument parsing
- Return namespace with typed attributes
- Validate source and destination formats in direction.py (not in CLI)
