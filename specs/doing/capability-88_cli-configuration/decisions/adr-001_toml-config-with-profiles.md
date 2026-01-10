# ADR 001: TOML-Based Configuration with Profiles

## Problem

cloud-mirror requires rclone config path on every invocation, and common dataset/remote pairs must be manually typed repeatedly. TrueNAS SCALE deployments only have Python 3.11 and git (no pip/uv), preventing traditional package installation with entry points in system PATH.

## Context

- **Business**: Operators run cloud-mirror in cron jobs, where verbose commands (~120 chars) are error-prone and hard to maintain. Common backup tasks (photos, documents, etc.) should be repeatable with short commands.
- **Technical**: Python 3.11 on TrueNAS SCALE includes `tomllib` for TOML parsing (stdlib, no external deps). Existing `cloud_mirror` package uses `pyproject.toml` with `[project.scripts]` entry, but `pip install` isn't available on production systems. Installation is manual copy to `/mnt/tank/apps/cloud-mirror/`.

## Decision

**Use TOML configuration files with named profiles for default options and common source/destination pairs, searched relative to the package installation directory.**

## Rationale

We need a configuration format that:

1. Works with Python 3.11 stdlib only (no external dependencies)
2. Supports both default options and named profiles
3. Can be located relative to the installation directory (which varies per deployment)
4. Allows partial specifications (source-only, destination-only, or both)

**Why TOML over alternatives:**

- **vs JSON**: TOML supports comments and is more human-friendly for operators editing configs. Python 3.11+ includes `tomllib` in stdlib.
- **vs YAML**: Requires external dependency (`pyyaml`). TrueNAS SCALE has no pip.
- **vs INI (configparser)**: Less structured, no native support for nested sections like `[profiles.photos]`. TOML's table syntax is clearer.
- **vs environment variables**: Cannot express profiles or nested config. Poor UX for multiple backup jobs.

**Why relative path search:**

TrueNAS SCALE installations use dataset-based paths like `/mnt/tank/apps/cloud-mirror/` that vary per deployment. Searching relative to package location (where `cloud_mirror/` directory lives) makes configs portable without hardcoded paths.

**Why profiles with optional source/destination:**

Operators have three use cases:

1. Fixed dataset → multiple remotes (e.g., `tank/photos` → `dropbox:photos` vs `b2:photos`)
2. Multiple datasets → fixed remote (e.g., `tank/photos`, `tank/docs` → `dropbox:backup/`)
3. Fully paired dataset+remote (e.g., `tank/critical` → `dropbox:critical-backup`)

Allowing profiles to specify `source`, `destination`, or both handles all three cases with CLI args filling in the blanks.

## Trade-offs Accepted

- **TOML is read-only in Python 3.11**: `tomllib` can only read TOML, not write it. Operators must manually create/edit `cloud-mirror.toml`.
  - *Mitigation*: Provide example config in documentation. TOML syntax is simple and human-friendly.

- **Profile name collisions**: If two profiles have the same name, last one wins (TOML spec).
  - *Mitigation*: Document that profile names must be unique. Validation warning on duplicate detection.

- **Relative path fragility if wrapper is moved**: If the wrapper script is copied (not symlinked) away from the package, path detection breaks.
  - *Mitigation*: Wrapper should resolve symlinks with `Path(__file__).resolve()`. Document that `--config` flag always works as fallback.

## Testing Strategy

### Level Coverage

| Level           | Question Answered                                                        | Scope                                            |
| --------------- | ------------------------------------------------------------------------ | ------------------------------------------------ |
| 1 (Unit)        | Does TOML parsing, path search logic, and config merging work correctly? | `config.py` module (parse, search, merge)        |
| 2 (Integration) | Does the wrapper find configs when symlinked and merge with CLI args?    | Wrapper script + config module + CLI integration |
| 3 (E2E)         | Does a cron job on TrueNAS-like environment work with profiles?          | Full deployment scenario                         |

### Escalation Rationale

- **1 → 2**: Unit tests cannot verify wrapper script symlink resolution or real filesystem search behavior. Integration tests confirm the wrapper locates the package and config files correctly when invoked from different directories.
- **2 → 3**: Integration tests cannot verify behavior on TrueNAS SCALE with only Python 3.11 stdlib. E2E tests confirm zero external dependencies and PATH installation works.

### Test Harness

| Level | Harness               | Location/Dependency                                |
| ----- | --------------------- | -------------------------------------------------- |
| 1     | Real temp files       | pytest `tmp_path` fixture with real TOML files     |
| 2     | Temporary install dir | tempfile with symlinked wrapper + real TOML files  |
| 3     | Simulated TrueNAS env | Container or VM with Python 3.11 only, no packages |

### Behaviors Verified

**Level 1 (Unit):**

- TOML parsing extracts `[defaults]` and `[profiles.*]` sections correctly
- Config search finds TOML in package directory before falling back to rclone default
- Config merging applies precedence: defaults → profile → CLI args
- Profile with `source` only merges with CLI destination arg
- Profile with `destination` only merges with CLI source arg
- Profile with both `source` and `destination` works standalone or overridden by CLI

**Level 2 (Integration):**

- Wrapper script resolves symlink to find package directory
- TOML config found relative to package location, not current working directory
- `--profile` flag loads profile settings and merges with CLI args
- CLI positional args override profile source/destination
- Missing TOML file falls back gracefully (no error, uses CLI args only)
- Malformed TOML file produces clear error message with line number

**Level 3 (E2E):**

- Cron job invokes symlinked wrapper with `--profile`, completes successfully
- Config auto-detected without `--config` flag
- Profile settings applied (visible in verbose output)
- Tool runs with Python 3.11 stdlib only (no pip packages)

## Validation

### How to Recognize Compliance

You're following this decision if:

- All config loading goes through `cloud_mirror.config.load_config()`
- TOML files use `[defaults]` and `[profiles.NAME]` sections
- Config search checks package directory before `~/.config/rclone/`
- CLI args override profile settings (tested)

### MUST

- Use `tomllib.load()` for TOML parsing (stdlib, Python 3.11+)
- Search for TOML config relative to package directory first
- Apply merge order: defaults → profile → CLI args
- Resolve symlinks with `Path(__file__).resolve()` in wrapper
- Validate profile structure (warn on unknown keys)

### NEVER

- Import external TOML libraries (`toml`, `tomlkit`) — use stdlib only
- Hardcode config paths — always search relative to package
- Silently ignore malformed TOML — report clear error with line number
- Let profile settings override explicit CLI args — CLI always wins
