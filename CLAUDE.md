# CLAUDE.md - zpool-status

## What Is This Project?

**zpool-status** provides enhanced ZFS pool status output for TrueNAS SCALE, augmenting `zpool status` with disk identification (model, serial number) via `smartctl`.

**Target Environment**: TrueNAS SCALE (Linux, Python 3.11, native ZFS, smartmontools pre-installed)

## Project Structure

```
zpool-status/
├── CLAUDE.md              # This file
├── pyproject.toml         # Project config (use with uv or pip)
├── zpool_status/          # Main package
│   ├── __init__.py
│   ├── __main__.py        # python -m zpool_status
│   ├── main.py            # CLI entry point (zstat command)
│   └── status.py          # Core: parse zpool status, enrich with smartctl
└── tests/
    └── test_status.py     # Unit tests (mocked subprocess calls)
```

## Usage

```bash
# On TrueNAS SCALE:
zstat status [pool]    # Enhanced zpool status with MODEL and SERIAL columns
```

## Development

```bash
# Run tests (macOS or any platform — no ZFS required, all mocked)
uv run --extra dev pytest tests/ -v

# Install in dev mode
uv pip install -e ".[dev]"
```

## Key Design Decisions

- **smartctl for disk info**: Most reliable source on TrueNAS SCALE (smartmontools pre-installed)
- **No external dependencies**: stdlib only — runs on TrueNAS's system Python without pip install
- **Zero ZFS required for tests**: All subprocess calls are mocked, tests run anywhere

## Always use `AskUserQuestion` Tool

**Always use the `AskUserQuestion` tool to obtain guidance from the user, such as: discover context, obtain rationale, as well as to support the user in making the right call by asking critical questions before blindly following the user's requests**

**NEVER ask the user any questions without using the `AskUserQuestion` tool**
