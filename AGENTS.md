# AGENTS.md - AI Agent Primer for cloud-mirror

**Single Entry Point**: This document provides essential context and pointers for further reading. You are expected to consume referenced documents without being asked.

## 🎯 What Is This Project?

**cloud-mirror** syncs ZFS datasets to cloud storage (Dropbox) via rclone, preserving the snapshot-based structure of ZFS.

**Current State**: `dropbox-push.py` is a working 1400-line script that implements push functionality. It works but lacks tests and is not modular. The goal is to extract this into a testable `cloud-mirror.py` module while adding pull capability.

**The Challenge**: ZFS doesn't run on macOS natively, so we need a Colima VM with ZFS installed just to run tests. This is why capability-10 (test infrastructure) must complete before capability-27 (push) or capability-54 (pull).

## 🚨 CRITICAL FIRST ACTIONS (DO THIS BEFORE ANYTHING ELSE)

**Before writing ANY code or making ANY changes:**

1. **READ `/context/1-structure.md`** - Understand work item hierarchy (Capability → Feature → Story), BSP numbering, and test lifecycle
2. **READ `/context/2-workflow.md`** - Understand how tests define DONE at each level
3. **INSPECT `/specs/doing/`** - Identify active work and current state (see State Detection below)

**These documents are AUTHORITATIVE. Code adapts to specs, not the other way around.**

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
- [ ] **Ran existing tests?** `uv run --with pytest pytest specs/ -v` to see current state
- [ ] **Using uv?** NEVER use pip. Always `uv run --with pytest pytest ...`

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

```bash
# Run all tests (some may skip if VM not running)
uv run --with pytest pytest specs/ -v

# Run only non-ZFS tests (no VM required)
uv run --with pytest pytest specs/ -v -m "not zfs"

# Run ZFS tests (requires VM with testpool)
uv run --with pytest pytest specs/ -v -m "zfs"

# Run specific story tests
uv run --with pytest pytest specs/doing/capability-10_colima-test-environment/feature-32_colima-zfs-environment/ -v
```

### VM Detection Pattern

Tests check if Colima VM is running with:

```python
result = subprocess.run(["colima", "status", "--profile", "zfs-test"], ...)
return "is running" in result.stdout.lower()
```

## 📋 Current Capabilities

### Capability 10: Colima Test Environment (Foundation)

**Purpose**: Enable ZFS testing on macOS via Colima VM
**Status**: Feature-32 in progress (stories have tests, running them)
**Why First**: Without this, we cannot run any tests that touch ZFS

### Capability 27: Dropbox Push

**Purpose**: Extract `dropbox-push.py` functionality into testable `cloud-mirror.py`
**Reference**: `dropbox-push.py` is the working implementation to be refactored
**Status**: Specs written, implementation pending (blocked by capability-10)

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

## ✅ Pre-Commit Checklist

- [ ] **Tests pass**: `uv run --with pytest pytest specs/ -v`
- [ ] **No hardcoded strings**: Check for magic values
- [ ] **Follows context/ standards**: Especially testing patterns

## 📚 When to Read Additional Context

| Trigger | Read This |
|---------|-----------|
| Creating new work items | `/context/1-structure.md` (BSP numbering) |
| Writing tests | `/context/4-testing-standards.md` |
| Making commits | `/context/5-commit-standards.md` |
| Confused about workflow | `/context/2-workflow.md` |
