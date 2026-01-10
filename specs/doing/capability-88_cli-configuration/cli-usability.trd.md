# Technical Requirements Document (TRD): CLI Usability

> **Purpose**: This is an unbounded "wishful thinking" catalyst, NOT a work item.
>
> - No size constraints, no state assessment (OPEN/IN PROGRESS/DONE)
> - User evaluates value BEFORE decomposition begins
> - Spawns sized work items (features/stories) AFTER value confirmed
> - Lives inside capability-88_cli-configuration as optional catalyst

## Status of this Document: DoR Checklist

| DoR checkbox          | Description                                                       |
| --------------------- | ----------------------------------------------------------------- |
| [x] **Outcome**       | Simplified CLI invocation and configuration management            |
| [x] **Test Evidence** | E2E tests proving executable wrapper, config resolution, profiles |
| [x] **Assumptions**   | Python 3.11 stdlib only (TrueNAS SCALE constraint)                |
| [x] **Dependencies**  | Existing cloud_mirror package, pyproject.toml scripts entry       |
| [x] **Pre-Mortem**    | Path detection fragility, TOML parsing edge cases                 |

## Problem Statement

### Technical Problem

```
When operators deploy cloud-mirror on TrueNAS SCALE, they encounter:
1. Verbose invocation: `python3 -m cloud_mirror` required for every run
2. Repetitive config flags: `--config /mnt/tank/apps/cloud-mirror/rclone.conf` on every command
3. No profile support: Cannot save common dataset/remote pairs for reuse
because TrueNAS SCALE provides only Python 3.11 and git (no pip/uv),
which blocks using a proper CLI installation method and requires manual
path management.
```

### Current Pain

- **Symptom**: Cron jobs use verbose `python3 -m cloud_mirror` commands with full paths
- **Root Cause**: No standalone executable, no config file search, no saved profiles
- **Impact**:
  - Long, error-prone cron job commands (~120 characters)
  - Config path must be specified on every invocation
  - Common dataset/remote pairs must be typed repeatedly

## Solution Design

### Technical Solution

```
Create a standalone executable wrapper (`cloud-mirror` script) that:
1. Detects its installation directory and searches for config files relative to that location
2. Supports TOML config files with default options and named profiles
3. Allows profiles to specify source, destination, or both
4. Merges config file settings with command-line arguments (CLI takes precedence)

All using Python 3.11 standard library (no external dependencies).
```

### Technical Architecture

**Components:**

1. **Standalone Wrapper** (`cloud-mirror` script at project root)
   - Shebang: `#!/usr/bin/env python3`
   - Detects script location: `Path(__file__).resolve().parent`
   - Adds `cloud_mirror/` to `sys.path`
   - Invokes `cloud_mirror.main:main()`
   - Can be symlinked to writable paths like `/mnt/tank/bin/cloud-mirror`

2. **Config Path Resolution** (new `cloud_mirror/config.py` module)
   - Detect package location relative to wrapper script
   - Search paths (in order):
     1. CLI `--config` flag (highest priority)
     2. `<package_dir>/cloud-mirror.toml` (if exists)
     3. `<package_dir>/rclone.conf` (for rclone config)
     4. `~/.config/rclone/rclone.conf` (rclone default, lowest priority)
   - Return resolved paths for both TOML config and rclone config

3. **TOML Config Support** (Python 3.11 includes `tomllib`)
   ```toml
   # cloud-mirror.toml example
   [defaults]
   transfers = 64
   tpslimit = 12
   keep_versions = 3

   [rclone]
   config = "./rclone.conf" # Relative to TOML file location

   [profiles.photos]
   remote = "dropbox-photos:backup"
   keep_versions = 5

   [profiles.docs]
   source = "tank/documents"
   remote = "dropbox-docs:backup"

   [profiles.full-backup]
   source = "tank/data"
   destination = "dropbox:full-backup"
   ```

4. **Config Merging Logic** (in `cloud_mirror/config.py`)
   - Load TOML config (if exists)
   - If `--profile NAME` specified, extract profile settings
   - Merge order (later overrides earlier):
     1. TOML `[defaults]` section
     2. TOML `[profiles.NAME]` section (if `--profile` specified)
     3. Command-line arguments
   - Profile can specify `source`, `destination`, or both
   - CLI positional args override profile source/destination

5. **CLI Integration** (extend `cloud_mirror/cli.py`)
   - Add `--profile NAME` optional argument
   - Keep existing `source` and `destination` positional args
   - If profile specifies source/dest and CLI provides them, CLI wins
   - Pass resolved config to existing direction detection and run_push/run_pull

**Data Flow:**

```
1. Wrapper script invoked: cloud-mirror tank/photos --profile photos
2. Config module loads TOML from package directory
3. Extract defaults, then profile "photos" settings
4. CLI parser sees positional "tank/photos", merges with profile remote
5. Final config: source="tank/photos", remote="dropbox-photos:backup", keep_versions=5
6. Existing direction detection and execution proceeds unchanged
```

## Expected Outcome

### Technical Capability

```
The system will provide:
1. A standalone `cloud-mirror` executable for PATH installation
2. Automatic rclone config path resolution relative to installation directory
3. TOML-based configuration with profiles for common use cases
4. Config merging with CLI precedence

This enables operators to:
- Use short commands: `cloud-mirror tank/photos dropbox:backup` (no python3 -m)
- Use profiles: `cloud-mirror tank/photos --profile photos` (remote auto-filled)
- Skip `--config` flag when using standard locations (auto-detected)
- Reduce cron command length from ~120 to ~50 characters

All with Python 3.11 stdlib only (no pip/uv on TrueNAS SCALE).
```

### Evidence of Success (BDD Tests)

- [ ] **Standalone Wrapper**: `cloud-mirror` script runs without `python3 -m`
- [ ] **Config Auto-Detection**: rclone config found relative to package location
- [ ] **TOML Profiles**: `--profile photos` loads settings from config
- [ ] **Config Merging**: CLI args override profile settings correctly
- [ ] **No External Deps**: All code uses Python 3.11 stdlib only

## Dependencies

### Work Item Dependencies

- None (builds on existing `cloud_mirror` package)

### Technical Dependencies

- **Required**: Python 3.11+ (stdlib only - specifically `tomllib` for TOML parsing)
- **Existing**: `cloud_mirror.cli`, `cloud_mirror.main`
- **New**: `cloud_mirror.config` module (for TOML loading, path resolution, config merging)

## Pre-Mortem Analysis

### Assumption: Script location detection fails in symlinked scenarios

- **Likelihood**: Medium
- **Impact**: Medium (config not auto-detected, user must use `--config`)
- **Mitigation**:
  - Use `Path(__file__).resolve()` to resolve symlinks to actual script location
  - Fall back to `~/.config/rclone/rclone.conf` if package-relative search fails
  - Document that `--config` flag always works as explicit override
  - Test with symlinked wrapper in different directories

### Assumption: TOML parsing errors on malformed config

- **Likelihood**: Low
- **Impact**: High (tool unusable if TOML syntax wrong)
- **Mitigation**:
  - Wrap `tomllib.load()` in try/except with clear error message showing line number
  - Validate required profile keys before merging (warn on unknown keys)
  - Provide example `cloud-mirror.toml` in documentation
  - If TOML file is malformed, skip it and continue (warning message only)

### Assumption: Profile source/destination conflicts with positional args

- **Likelihood**: Medium
- **Impact**: Low (user confusion about which takes precedence)
- **Mitigation**:
  - Clear precedence rules documented: CLI positional args always override profile
  - Verbose mode shows merged config with source of each value
  - Error message if profile has both source+dest but CLI also provides both (ambiguous intent)
