# AGENTS.md - AI Agent Primer for cloud-mirror

**Single Entry Point**: This document provides essential context and pointers for further reading. You are expected to consume referenced documents without being asked.

## 🎯 What Is This Project?

**cloud-mirror** syncs ZFS datasets to cloud storage (Dropbox) via rclone, preserving the snapshot-based structure of ZFS.

**Current State**: `dropbox-push.py` is a working 1400-line script that implements push functionality. It works but lacks tests and is not modular. The goal is to extract this into a testable `cloud-mirror.py` module while adding pull capability.

**The Challenge**: ZFS doesn't run on macOS natively, so we need a Colima VM with ZFS installed just to run tests. This is why capability-10 (test infrastructure) must complete before capability-27 (push) or capability-54 (pull).

## 🖥️ Development vs Production Environments

**This distinction is critical for understanding the test infrastructure.**

| Aspect      | Development (macOS)    | Production (TrueNAS SCALE) |
| ----------- | ---------------------- | -------------------------- |
| **ZFS**     | Inside Colima VM       | Native (Linux kernel)      |
| **Colima**  | Required for testing   | Not present                |
| **Tests**   | Run here only          | Never run in production    |
| **rclone**  | Mock remote (local fs) | Real Dropbox remote        |

**Why this matters:**

- All ZFS tests execute commands **inside the Colima VM** via SSH
- The `tests/` directory and pytest fixtures are **dev-only infrastructure**
- Production runs `cloud-mirror.py` directly on TrueNAS where ZFS is native
- Never assume ZFS commands run locally on the dev machine

## 🚨 CRITICAL FIRST ACTIONS (DO THIS BEFORE ANYTHING ELSE)

**Before writing ANY code or making ANY changes:**

1. **READ `/context/1-structure.md`** - Understand work item hierarchy (Capability → Feature → Story), BSP numbering, and test lifecycle
2. **READ `/context/2-workflow.md`** - Understand how tests define DONE at each level
3. **INSPECT `/specs/doing/`** - Identify active work and current state (see State Detection below)

**These documents are AUTHORITATIVE. Code adapts to specs, not the other way around.**

## 🔍 Environment Verification (Do This First)

**Before doing ANY work, verify the environment is healthy:**

```bash
# 1. Verify uv works
uv run --extra dev pytest --version

# 2. Check VM status
colima status --profile zfs-test

# 3. Run graduated environment tests (ALL should PASS, not skip)
uv run --extra dev pytest tests/environment/ -v

# 4. Run story tests in development
uv run --extra dev pytest specs/ -v
```

**If environment tests skip or fail:**

- Tests skipping → VM not running or ZFS not installed (run setup scripts)
- Tests failing → Environment issue needs debugging (see Known Gotchas below)

## 🚨 STATE DETECTION: Where Did We Leave Off?

**The state of work is encoded in the filesystem, not in comments or notes.**

### Work Item State (from `tests/` directory)

| State | `tests/` Directory | Meaning | Next Action |
|-------|-------------------|---------|-------------|
| 1 | Missing or empty | Not started | Write failing tests (RED) |
| 2 | Has test files, no `DONE.md` | In progress | Run tests, fix failures, implement |
| 3 | Has `DONE.md` | Complete | Move to next work item |

### Execution Order

- **Lower-numbered items complete before higher-numbered** (story-32 before story-54)
- **Children must complete before parent is DONE** (all stories done → feature done)

### To Find Current Work

```bash
# List all work items with test state
find specs/doing -name "tests" -type d -exec sh -c 'echo "{}:" && ls -la "{}" 2>/dev/null | head -5' \;

# Find incomplete work (has tests but no DONE.md)
find specs/doing -name "tests" -type d ! -exec test -f "{}/DONE.md" \; -print
```

## 🚨 BEFORE YOU CODE - QUICK CHECKLIST

- [ ] **Read context/?** Read `1-structure.md` and `2-workflow.md` completely
- [ ] **Identified current work?** Check `specs/doing/` for in-progress items
- [ ] **Story exists?** If implementing code, verify the story exists. **NO CODE WITHOUT A STORY.** Create the story first if missing.
- [ ] **Ran existing tests?** `uv run --extra dev pytest specs/ -v` to see current state
- [ ] **Using uv?** NEVER use pip. Always `uv run --extra dev pytest ...`

## 📁 Project Structure

```
cloud-mirror/
├── AGENTS.md                    # THIS FILE - Start here
├── dropbox-push.py              # Working script (capability-27 reference implementation)
├── cloud-mirror.py                      # Target: testable module (does not exist yet)
├── pyproject.toml               # Python project config (use with uv)
├── scripts/
│   ├── start-test-vm.sh         # Start Colima VM for ZFS testing
│   ├── setup-zfs-vm.sh          # Install ZFS in Colima VM
│   └── create-test-pool.sh      # Create testpool in VM
├── tests/
│   ├── conftest.py              # Pytest fixtures (ZFS, rclone mocks)
│   └── rclone-test.conf         # Mock rclone remote (local backend)
├── context/                     # 🚨 READ FIRST - Universal guidance
│   ├── 1-structure.md           # Work item hierarchy, BSP numbering
│   ├── 2-workflow.md            # Requirements → Decisions → Work Items
│   ├── 3-coding-standards.md    # Type annotations, style
│   ├── 4-testing-standards.md   # BDD methodology, test levels
│   ├── 5-commit-standards.md    # Conventional commits
│   └── templates/               # Document templates
└── specs/doing/                 # 🚨 ACTIVE WORK - Check state here
    ├── capability-10_colima-test-environment/
    │   ├── colima-test-environment.capability.md
    │   ├── decisions/
    │   │   └── adr-001_colima-zfs-environment.md
    │   ├── feature-32_colima-zfs-environment/
    │   │   ├── colima-zfs-environment.feature.md
    │   │   ├── story-32_colima-setup/
    │   │   │   ├── colima-setup.story.md
    │   │   │   └── tests/           # ← Check for DONE.md
    │   │   ├── story-54_zfs-installation/
    │   │   └── story-76_test-pool-creation/
    │   ├── feature-54_pytest-fixtures/
    │   └── feature-76_mock-rclone-remote/
    ├── capability-27_dropbox-mirror-push/
    │   └── [features for push - extract from dropbox-push.py]
    └── capability-54_dropbox-mirror-pull/
        └── [features for pull - new functionality]
```

## 🔧 Development Environment

### Prerequisites

- **macOS with Homebrew**
- **Colima**: `brew install colima` (NOT Docker Desktop - see ADR-001)
- **uv**: `brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`

### Setting Up Test Environment (ZFS in Colima VM)

```bash
# 1. Start the Colima VM
./scripts/start-test-vm.sh

# 2. Install ZFS in the VM
./scripts/setup-zfs-vm.sh

# 3. Create the test pool
./scripts/create-test-pool.sh

# Verify
colima ssh --profile zfs-test -- zfs list testpool
```

### Running Tests

Tests live in TWO locations:

```bash
# 1. GRADUATED tests (regression protection) - run FIRST
uv run --extra dev pytest tests/ -v

# 2. STORY tests in development
uv run --extra dev pytest specs/ -v

# Run both together
uv run --extra dev pytest tests/ specs/ -v

# Run only non-VM tests (no VM required)
uv run --extra dev pytest tests/ specs/ -v -m "not vm_required"

# Run VM tests only (requires VM with testpool)
uv run --extra dev pytest tests/ specs/ -v -m "vm_required"
```

**Why `--extra dev`?** pytest is declared in `[project.optional-dependencies]` under `dev` in `pyproject.toml`. Using `--extra dev` tells uv to install dev dependencies and use them from the project's `.venv`, bypassing any system Python or pyenv shims.

### VM Detection Pattern

Tests check if Colima VM is running with:

```python
result = subprocess.run(["colima", "status", "--profile", "zfs-test"], ...)
# Note: colima status outputs to stderr, not stdout
combined_output = (result.stdout + result.stderr).lower()
return result.returncode == 0 and "is running" in combined_output
```

### ⚠️ Known Gotchas

**These non-obvious issues have caused debugging headaches:**

| Issue | Symptom | Solution |
| ----- | ------- | -------- |
| `colima status` outputs to stderr | VM detection fails even when VM running | Check `stderr`, not just `stdout` |
| pyenv shims intercept commands | `pytest: command not found` even with uv | Use `uv run --extra dev pytest` (not `--with`) |
| Stale `VIRTUAL_ENV` from other projects | uv uses wrong venv, commands fail | Run `unset VIRTUAL_ENV` or start fresh shell |
| ZFS commands need sudo in VM | Permission denied on zfs create/destroy | Prefix with `sudo` inside VM |

## 📋 Current Capabilities

> **Note:** Status below may be stale. Check `tests/DONE.md` files in each story to verify actual completion state.

### Capability 10: Colima Test Environment (Foundation)

**Purpose**: Enable ZFS testing on macOS via Colima VM
**Status**: ✅ COMPLETE - All features done (Feature-32, Feature-54, Feature-76 have DONE.md)
**Why First**: Without this, we cannot run any tests that touch ZFS

### Capability 27: Dropbox Push

**Purpose**: Extract `dropbox-push.py` functionality into testable `cloud-mirror.py`
**Reference**: `dropbox-push.py` is the working implementation to be refactored
**Status**: Ready to start (unblocked by capability-10)

### Capability 54: Dropbox Mirror Pull

**Purpose**: Add pull direction to `cloud-mirror.py` (remote → ZFS)
**Status**: Specs written, implementation pending (blocked by capability-10)

## 🧠 Key Concepts

### Clone Tree Approach (Push)

Rather than traversing `.zfs/snapshot/` (which shows live child dataset mountpoints), we create clones from recursive snapshots, providing an immutable, consistent view.

### Direction Detection (cloud-mirror.py)

Auto-detect push vs pull based on argument order:

- `cloud-mirror.py dataset remote` → PUSH (ZFS to Dropbox)
- `cloud-mirror.py remote dataset` → PULL (Dropbox to ZFS)

Detection: rclone remotes have format `remote:path`, ZFS datasets are `pool/dataset`.

### Pre-Pull Snapshot (Pull)

Pull operations create a snapshot before syncing, enabling rollback:

```bash
zfs rollback testpool/target@dropboxpull-pre-TIMESTAMP
```

## 🔄 Workflow Summary

From `/context/2-workflow.md`:

1. **Capability** = E2E tests define DONE
2. **Feature** = Integration tests define DONE
3. **Story** = Makes tests go RED → GREEN

**Stories are ORDERED**: Story N assumes stories 1..N-1 complete.

## 🎓 Story Completion & Test Graduation

**A story is NOT complete until its tests are graduated.** See `/context/2-workflow.md` for full details.

### Graduation Process

1. **Code is production-ready** - Fully refactored, no TODOs
2. **Tests move** from `specs/doing/.../story-XX/tests/` → `tests/`
3. **Tests are ordered** for regression detection:
   - Trivial checks first (early warning signs)
   - More involved tests follow
4. **DONE.md created** in story's `tests/` directory documenting:
   - Where graduated tests now live in `tests/`
   - Any tests remaining in specs and rationale

### Test Directory Structure

```
tests/
├── conftest.py              # Shared fixtures (VM helpers, ZFS commands)
├── environment/             # Environment verification (graduated from capability-10)
│   ├── test_colima.py       # Colima available and running
│   ├── test_zfs_in_vm.py    # ZFS installed in VM
│   ├── test_pool.py         # testpool exists and healthy
│   └── test_rclone.py       # rclone mock remote available
├── fixtures/                # Fixture verification (graduated from capability-10)
│   ├── test_zfs_fixtures.py # zfs_dataset, zfs_dataset_with_children
│   └── test_sample_files.py # sample_files_in_tmp
└── rclone-test.conf         # Mock rclone remote config
```

## ✅ Pre-Commit Checklist

- [ ] **Graduated tests pass**: `uv run --extra dev pytest tests/ -v`
- [ ] **Story tests pass**: `uv run --extra dev pytest specs/ -v`
- [ ] **No hardcoded strings**: Check for magic values
- [ ] **Follows context/ standards**: Especially testing patterns

## 📚 When to Read Additional Context

| Trigger                      | Read This                                    |
| ---------------------------- | -------------------------------------------- |
| Creating new work items      | `/context/1-structure.md` (BSP numbering)    |
| Writing tests                | `/context/4-testing-standards.md`            |
| Making commits               | `/context/5-commit-standards.md`             |
| Confused about workflow      | `/context/2-workflow.md`                     |
| Completing a story           | `/context/2-workflow.md` (Test Graduation)   |
