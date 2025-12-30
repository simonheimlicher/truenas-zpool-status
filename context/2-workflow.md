# Workflow: From Vision to Validated Code

## Overview

This workflow transforms a naive vision into validated, working code through three phases:

1. **Requirements** (PRD/TRD) - Capture the vision
2. **Decisions** (ADR) - Constrain architecture
3. **Work Items** (Capability/Feature/Story) - Sized, testable implementation

```
┌─────────────────────────────────────────────────────────────┐
│                      REQUIREMENTS                           │
│  PRD (user-focused)              TRD (system-focused)       │
│  "What users want"               "What system needs"        │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                       DECISIONS                             │
│  ADR (architecture)                                         │
│  "HOW we build it" - at project, capability, or feature     │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      WORK ITEMS                             │
│  Capability ──► Feature ──► Story                           │
│  (E2E tests)   (Integration)  (Incremental)                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Requirements (Vision)

**PRD and TRD capture the vision without implementation constraints.**

### PRD - Product Requirements Document

- **Audience**: Users, stakeholders
- **Focus**: What users want and why
- **Size**: Unbounded - can be any scope
- **No tests** - it's just vision

Example:

```
Users want to sync their ZFS datasets to Dropbox so they can:
- Have off-site backups of important data
- Preserve the snapshot history structure
- Easily restore from any point in time
```

### TRD - Technical Requirements Document

- **Audience**: Developers, system designers
- **Focus**: What the system needs to do
- **Size**: Unbounded - can be any scope
- **No tests** - it's just vision

Example:

```
The system must:
- Create recursive ZFS snapshots before sync
- Build clone trees to provide immutable view of snapshot data
- Sync via rclone to cloud remotes (Dropbox, etc.)
- Support both push (ZFS → cloud) and pull (cloud → ZFS) directions
- Clean up clones after successful sync
```

**Output**: A vision document that says WHAT and WHY, not HOW or WHEN.

---

## Phase 2: Decisions (Constraints)

**ADRs constrain the vision into something implementable.**

### ADR - Architecture Decision Record

- **Purpose**: Technical decisions - HOW to build it
- **Constrains**: Implementation approach
- **Enables future flexibility**

Example:

```
ADR-001: Clone Tree Approach for Snapshot Sync

Decision: Create clones from recursive snapshots rather than traversing .zfs/snapshot/.

Consequences:
- Provides immutable, consistent view of snapshot data
- Child dataset mountpoints show snapshot state, not live data
- Requires cleanup of clones after sync
- Uses more temporary disk space during sync

Trade-off: Extra disk space and cleanup complexity enables correct snapshot traversal.
```

### ADR Scope Levels

ADRs can live at three levels:

| Level          | Location                   | Example                                      |
| -------------- | -------------------------- | -------------------------------------------- |
| **Project**    | `specs/decisions/`         | "Use Colima VM for ZFS testing on macOS"     |
| **Capability** | `capability-NN/decisions/` | "Clone tree approach for snapshot sync"      |
| **Feature**    | `feature-NN/decisions/`    | "Use rclone sync with --checksum flag"       |

Narrower scope inherits from broader. Stories don't have ADRs—they inherit from their parent feature
and capability.

**Output**: Decisions that constrain the vision into a sized, implementable plan.

---

## Phase 3: Work Items (Implementation)

**Capabilities, Features, and Stories are SIZED containers with TESTS.**

### Sizing the Work

Given decisions, decompose into work items:

| PRD/TRD Scope | Might Become                             |
| ------------- | ---------------------------------------- |
| Small vision  | 1 capability, 2-3 features, 5-10 stories |
| Medium vision | 2-3 capabilities, 5-8 features each      |
| Large vision  | 10+ capabilities over multiple releases  |

**The decomposition depends on decisions made in ADRs.**

### Capability (E2E Scenario)

- **Size**: Substantial work, multiple features
- **Test**: End-to-end scenario proving the capability works
- **Definition**: When E2E test passes, capability is DONE

Write the E2E test FIRST:

```gherkin
Feature: Push ZFS Dataset to Dropbox

  Scenario: Push dataset with child datasets to cloud
    Given ZFS dataset "tank/photos" with children:
      | dataset          | has_snapshot |
      | tank/photos      | true         |
      | tank/photos/2023 | true         |
      | tank/photos/2024 | true         |
    And rclone remote "dropbox:backup" exists
    When I run: cloud-mirror.py tank/photos dropbox:backup
    Then Dropbox contains mirrored directory structure
    And all files match checksums
    And clones are cleaned up after sync
```

**This test won't run yet. That's the point.**

### Feature (Atomic Functionality of E2E Scenario)

- **Size**: Specific capability, multiple stories
- **Test**: Integration scenario proving components work together
- **Definition**: When integration tests pass, feature is DONE

Write integration tests that ENABLE the E2E test:

```gherkin
Feature: ZFS Snapshot Operations

  Scenario: Create recursive snapshot
    Given ZFS dataset "testpool/data" with children
    When create_recursive_snapshot() is called
    Then snapshot exists on parent and all children
    And all snapshots have matching timestamp suffix
```

```gherkin
Feature: Clone Tree Management

  Scenario: Build clone tree from snapshot
    Given recursive snapshot "testpool/data@sync-20240101"
    When build_clone_tree() is called
    Then clones are mounted at temporary location
    And child dataset mountpoints show snapshot data (not live)
```

```gherkin
Feature: Rclone Push Sync

  Scenario: Sync clone tree to remote
    Given clone tree mounted at "/tmp/sync-clones"
    And rclone remote "testremote:backup"
    When rclone_sync() is called
    Then remote contains all files from clone tree
    And checksums match
```

### Story (Atomic Deployable Functionality or Enabler)

- **Size**: Single sprint, independently deployable
- **Test**: Makes feature/E2E tests go RED → GREEN
- **Definition**: Story N assumes stories 1..N-1 are complete

**Stories are ORDERED. Each builds on the previous.**

| Order | Story                      | Enables                    | Test Status              |
| ----- | -------------------------- | -------------------------- | ------------------------ |
| 1     | Colima VM setup            | VM runs on macOS           | Compiles                 |
| 2     | ZFS installation in VM     | ZFS commands available     | Compiles                 |
| 3     | Test pool creation         | testpool exists            | 🟢 Colima feature        |
| 4     | create_recursive_snapshot  | Snapshots created          | Compiles                 |
| 5     | build_clone_tree           | Clone tree mounted         | 🟢 Clone tree feature    |
| 6     | rclone_sync                | Files synced to remote     | 🟢 Rclone feature        |
| 7     | cleanup_clones             | Clones destroyed           | Compiles                 |
| 8     | CLI integration            | Full push flow             | 🟢 **E2E capability**    |

**Each story's value = moving tests from RED to GREEN.**

---

## The Complete Flow

```
1. REQUIREMENTS
   └── PRD: "Users want to sync ZFS datasets to Dropbox"
   └── TRD: "System needs snapshot management, clone trees, rclone integration"

2. DECISIONS
   └── ADR (project): "Use Colima VM for ZFS testing on macOS"
   └── ADR (capability): "Clone tree approach for consistent snapshot view"

3. WORK ITEMS
   └── Capability 10: Colima Test Environment (FIRST - enables all other testing)
       └── Write E2E test scenario (won't pass yet)

       └── Feature: Colima ZFS Environment
           └── Write integration test (won't pass yet)
           └── Story 1: Colima VM setup
           └── Story 2: ZFS installation
           └── Story 3: Test pool creation
           └── ✅ Integration test passes

   └── Capability 27: Dropbox Push (blocked until Capability 10 done)
       └── Write E2E test scenario (won't pass yet)

       └── Feature: ZFS Snapshot Operations
           └── Story 4: create_recursive_snapshot
           └── ✅ Integration test passes

       └── Feature: Clone Tree Management
           └── Story 5: build_clone_tree
           └── Story 6: cleanup_clones
           └── ✅ Integration test passes

       └── Feature: Rclone Push Sync
           └── Story 7: rclone_sync
           └── ✅ Integration test passes

       └── Feature: Push CLI
           └── Story 8: CLI integration
           └── ✅ E2E test passes
           └── ✅ CAPABILITY DONE
```

---

## Key Principles

### Requirements Are Immutable

- **Work items exist to cover requirements**, not to describe existing code
- Whether code exists, is missing, or deviates is irrelevant to whether a work item should exist
- Requirements don't adapt to code—code adapts to requirements
- Any deviation from a requirement (documented in work item or ADR) = work to be done
- Any requirement fully met = no work needed

This means:

- A story for "extract build_clone_tree()" exists because the capability requires it, regardless of
  whether `dropbox-push.py` already has this logic embedded
- If existing code deviates from an ADR, the work item is to fix the deviation, not to update the
  ADR
- The presence of passing tests doesn't mean requirements are met—only alignment with documented
  requirements does

### Tests Are Requirements (at Work Item Level)

- PRD/TRD have no tests - they're vision
- Capabilities have E2E tests - they define DONE
- Features have integration tests - they define component behavior
- Stories make tests go RED → GREEN

### Decisions Enable Decomposition

- You can't size work without decisions
- ADRs constrain architecture → clearer implementation path
- Scope decisions emerge from PRD/TRD priorities and work item sizing

### Stories Are Incremental, Not Independent

- Story N assumes stories 1..N-1 are complete
- Each story adds value ON TOP of previous work
- Value = tests moving from RED to GREEN

### Write Tests Before Code

- Capability: E2E test scenario first
- Feature: Integration test scenarios first
- Story: Implement to make tests pass

### No Explicit References Between Work Items

- A feature MUST NOT reference its stories
- A capability MUST NOT reference its features
- Dependencies are encoded in hierarchy and numbering only (see
  [1-structure.md](./1-structure.md#implicit-dependencies-in-work-items))
- If a requirement appears uncovered, CREATE a new child work item—don't annotate the parent

This enables:

- Multiple agents to independently verify completeness
- No stale cross-references to maintain
- Work items that remain valid regardless of how children evolve

---

## Work Item Completion

Work item completion is determined by the file system state of the `tests/` directory within the
work item. This enables coordination across multiple AI agent sessions without explicit handover.

### Three-State Model

```
work-item/
├── work-item.{story|feature|capability}.md    # Requirements (immutable)
└── tests/                                      # State indicator
    ├── (empty or missing)                      # State 1: Not started
    ├── test_*.py                               # State 2: In progress
    └── DONE.md                                 # State 3: Complete
```

| State | `tests/` Directory           | Meaning          | Next Action                                 |
| ----- | ---------------------------- | ---------------- | ------------------------------------------- |
| 1     | Missing or empty             | Work not started | Write failing tests (RED)                   |
| 2     | Has test files, no `DONE.md` | Work in progress | Run tests, implement code (GREEN), refactor |
| 3     | Has `DONE.md`                | Complete         | Verify or move on                           |

### Completion by Work Item Level

| Level          | Own Tests          | `DONE.md` Proves                  | Child Verification                  |
| -------------- | ------------------ | --------------------------------- | ----------------------------------- |
| **Story**      | Unit + Integration | Tests graduated, requirements met | N/A                                 |
| **Feature**    | Integration        | Integration tests pass            | All `story-*/tests/DONE.md` exist   |
| **Capability** | E2E                | E2E tests pass                    | All `feature-*/tests/DONE.md` exist |

### DONE.md Structure

The `DONE.md` file serves as completion evidence. It lists graduated tests and verification of
non-functional requirements. See [templates](./templates/) for the full template.

```markdown
# Completion Evidence

## Graduated Tests

| Requirement      | Test Location                                  |
| ---------------- | ---------------------------------------------- |
| [From work item] | `tests/unit/test_xxx.py::TestClass::test_name` |

## Non-Functional Verification

| Standard               | Evidence                                        |
| ---------------------- | ----------------------------------------------- |
| Type annotations       | All functions annotated                         |
| Pydantic at boundaries | `tests/integration/test_xxx.py::test_validates` |
```

### Test Graduation

**Tests are not just verification—they are regression protection.** When a work item is complete, tests graduate from specs to the global `tests/` directory where they serve as early warning signs for regressions.

#### Graduation Steps

1. **Refactor code to production quality** - No TODOs, no hacks, fully typed
2. **Refactor tests for regression detection**:
   - Order tests from trivial to complex (trivial tests catch obvious breakage fast)
   - First test should verify basic availability (e.g., "is command available?")
   - Later tests verify functional behavior
3. **Move tests** from `specs/doing/.../story-XX/tests/` → `tests/{environment,unit,integration,e2e}/`
4. **Create DONE.md** in story's `tests/` directory documenting graduation

#### Test Ordering Strategy

Tests should be ordered to fail fast on environment issues:

```python
# Good ordering - trivial first
class TestColima:
    def test_colima_command_available(self):     # 1. Is tool installed?
        ...
    def test_colima_status_works(self):          # 2. Does basic command work?
        ...
    def test_vm_running(self):                   # 3. Is VM running?
        ...
    def test_can_ssh_to_vm(self):                # 4. Can we connect?
        ...
    def test_can_execute_command(self):          # 5. Does execution work?
        ...
```

#### DONE.md Contents

```markdown
# Completion Evidence: Story-XX

## Graduated Tests

| Requirement | Graduated To |
| ----------- | ------------ |
| FR1: ...    | `tests/environment/test_xxx.py::TestClass::test_name` |
| FR2: ...    | `tests/environment/test_xxx.py::TestClass::test_other` |

## Tests Remaining in Specs

| Test | Rationale |
| ---- | --------- |
| (none or list) | (why not graduated) |

## Verification

- All tests pass: `uv run --extra dev pytest tests/ -v`
- Code reviewed and refactored
```

#### Development vs Production Environments

**Critical context for understanding test infrastructure:**

| Aspect     | Development (macOS)    | Production (TrueNAS SCALE) |
| ---------- | ---------------------- | -------------------------- |
| **ZFS**    | Inside Colima VM       | Native (Linux kernel)      |
| **Colima** | Required for testing   | Not present                |
| **Tests**  | Run here only          | Never run in production    |
| **rclone** | Mock remote (local fs) | Real Dropbox remote        |

This means:

- All ZFS tests execute commands **inside the Colima VM** via SSH
- The `tests/` directory is **dev-only infrastructure**
- Production runs `cloud-mirror.py` directly on TrueNAS where ZFS is native
- Never assume ZFS commands run locally on the dev machine

### Filling Requirement Gaps

When an agent determines a parent's requirement is not covered by existing children:

1. **Do NOT modify the parent** work item to reference children
2. **CREATE a new child** work item (story for feature, feature for capability)
3. Use BSP numbering to insert the new child in the appropriate position
4. The new child's requirements should directly address the gap

This process may result in some redundant verification across agent sessions. This is
intentional—it's preferable to stale cross-references.

---

See [1-structure.md](./1-structure.md) for directory layout, naming conventions, and BSP numbering.
