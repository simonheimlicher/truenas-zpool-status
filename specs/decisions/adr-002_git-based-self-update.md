# ADR: Git-Based Self-Update Mechanism

## Problem

cloud-mirror runs on TrueNAS SCALE, which has git pre-installed but no pip or apt access (these are intentionally disabled to protect OS integrity). Users need a way to keep the tool updated without manual file copying or package management. How should cloud-mirror update itself in this constrained environment?

## Options Considered

### Option 1: Git-based updates

User installs via `git clone`, tool runs `git fetch origin && git pull --ff-only` to update itself. Updates applied by re-executing the script with the new code.

**Pros:**

- Git is pre-installed on TrueNAS SCALE
- Atomic operations (git pull is transactional)
- Built-in rollback via `git checkout <commit>`
- Transparent (users can inspect commits, diffs)
- Zero additional dependencies

**Cons:**

- Requires initial installation via git clone (not file copy)
- .git directory adds ~2-5MB disk overhead
- Requires network access for updates

### Option 2: GitHub API + tarball download

Check GitHub releases API for new versions, download and extract tarball to replace existing files.

**Pros:**

- Smaller footprint (no .git directory)
- Works with file-copy installation

**Cons:**

- Need to implement version comparison logic
- Tarball extraction is not atomic (partial updates possible)
- No built-in rollback mechanism
- Requires GitHub API access (additional complexity)
- Users can't easily inspect what changed

### Option 3: zipapp single-file distribution

Bundle entire package into `cloud-mirror.pyz` using Python's zipapp, download single file to update.

**Pros:**

- Simplest deployment (one file)
- Atomic replacement (single file copy)

**Cons:**

- Less transparent (bundled code harder to inspect)
- Complicates development workflow
- Requires build step for distribution
- Users can't easily see source code

## Decision

**We will use Option 1: Git-based updates.**

## Rationale

TrueNAS SCALE already has git installed, which provides exactly the functionality we need:

- **Atomic updates**: `git pull --ff-only` ensures we never end up with a partially-updated installation
- **Built-in safety**: Can detect uncommitted local changes and abort update
- **Zero dependencies**: No need to add requests/urllib3 for HTTP, no need for tarball handling
- **Rollback built-in**: `git checkout <tag>` for instant version switching
- **Transparent**: Users (and admins) can run `git log`, `git diff` to see exactly what changed

The disk overhead (~2-5MB for .git directory) is negligible on modern systems, and the transparency benefit outweighs this cost. Since cloud-mirror has zero runtime dependencies (stdlib-only), requiring git for installation/updates is a reasonable constraint.

For cron jobs, the `--no-update` flag ensures predictable behavior (no network calls, no code changes mid-operation).

## Trade-offs Accepted

- **Installation method constraint**: Users must install via `git clone`, not by copying files. This is acceptable because:
  - Git is already installed on TrueNAS
  - README will provide clear `git clone` instructions
  - Non-git installations will print helpful migration message

- **Network dependency**: Update checks require network access. This is mitigated by:
  - `--no-update` flag for offline/air-gapped systems
  - Graceful degradation (failed checks don't block sync)
  - Configurable check interval (default: once per 24 hours)

- **Disk overhead**: .git directory adds 2-5MB. This is acceptable because:
  - TrueNAS systems have ample storage
  - Transparency benefit outweighs cost
  - Users can see full commit history

## Constraints

- Installation MUST be via `git clone https://github.com/simonheimlicher/truenas-cloud-mirror.git`
- Update checks MUST be skippable via `--no-update` flag
- Updates MUST occur BEFORE sync operations begin, never mid-sync
- Failed updates MUST NOT block sync operations (graceful degradation)
- Update mechanism MUST check for uncommitted local changes and abort if dirty
- Re-execution pattern: After successful update, use `os.execv()` to restart with new code
