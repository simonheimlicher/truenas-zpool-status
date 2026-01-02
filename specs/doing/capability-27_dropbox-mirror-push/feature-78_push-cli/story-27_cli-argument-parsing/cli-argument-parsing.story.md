# Story: CLI Argument Parsing

## What Changes

Implement argument parsing for cloud-mirror.py push command using argparse.

## Functional Requirements

### FR1: Positional arguments for dataset and destination

```gherkin
GIVEN cloud-mirror.py script
WHEN executed with: cloud-mirror.py push testpool/data dropbox:backup
THEN args.dataset = "testpool/data"
AND args.destination = "dropbox:backup"
```

### FR2: Push-specific options

```gherkin
GIVEN cloud-mirror.py with options:
  | option          | default |
  | --keep-versions | 0       |
  | --keep-snapshot | false   |
  | --keep-clone    | false   |
  | --transfers     | 64      |
  | --tpslimit      | 12      |
  | --dry-run       | false   |
  | --config        | None    |
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

- Use argparse with subcommands (push, pull - future)
- Return namespace with typed attributes
- Validate dataset format (pool/path)
- Validate destination format (remote:path)
