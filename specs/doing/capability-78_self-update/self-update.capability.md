# Capability: Self-Update

## Observable Outcome

Users install cloud-mirror once via `git clone` and never need to manually update it. The tool automatically keeps itself current with the latest GitHub version while providing predictable behavior for automated cron jobs.

## Capability E2E Tests

### CE1: Interactive user gets silent auto-update

GIVEN cloud-mirror installed via git clone
AND a new version exists on GitHub (origin/main)
AND user runs interactive sync command (no flags)
WHEN cloud-mirror starts
THEN it silently fetches and applies the update
AND re-executes itself with new code
AND completes the sync operation
AND user sees no update prompts or confirmations

### CE2: Cron job runs with predictable version

GIVEN cloud-mirror scheduled in cron without `--update` flag
WHEN cron job executes
THEN no network requests are made for update checking
AND sync proceeds immediately with current version
AND execution time is consistent (no update delays)
AND no "update available" messages appear in logs

### CE3: Manual update check and apply

GIVEN cloud-mirror installed via git
WHEN user runs `cloud-mirror --check-update`
THEN current and remote versions are printed
AND no sync operation runs
AND when user runs `cloud-mirror --update`
THEN update is applied before sync
AND sync proceeds with new version

### CE4: Non-git installation guidance

GIVEN cloud-mirror installed by copying files (no .git directory)
WHEN user runs any sync command
THEN a warning appears with git clone instructions
AND sync proceeds normally with current version
AND no errors occur

## Features

This capability consists of:

- **Feature 27: Git-Based Update** - Core update mechanism using git fetch/pull
- **Feature 54: Update CLI Integration** - Command-line flags and user control
- **Feature 76: Update Orchestration** - Startup flow and re-execution logic

## Parent Capability Integration

This capability enhances all sync capabilities (push, pull) by ensuring the latest code is always used. It depends on:

- Repository hosted on GitHub (public read access)
- Git installed on target system (TrueNAS SCALE)
- Network connectivity (for update checks)

## Success Criteria

1. **Zero manual updates**: Users never copy files or run git commands manually
2. **Cron safety**: Scheduled jobs with `--no-update` have zero network overhead
3. **Graceful degradation**: Network failures or git errors don't block sync operations
4. **Transparency**: Users can see what changed via git log
5. **Rollback capability**: Users can `git checkout <tag>` to revert versions
