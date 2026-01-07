# Project Structure and Artifacts

## Artifact Layers

The project uses three layers of artifacts:

| Layer            | Documents                  | Purpose                          | Size Constrained? | Has Tests? |
| ---------------- | -------------------------- | -------------------------------- | ----------------- | ---------- |
| **Requirements** | PRD, TRD                   | Vision - WHAT and WHY            | No                | No         |
| **Decisions**    | ADR                        | Constraints - HOW to build it    | No                | No         |
| **Work Items**   | Capability, Feature, Story | Implementation - sized, testable | Yes               | Yes        |

See [2-workflow.md](./2-workflow.md) for how these layers connect.

---

## ⚠️ Critical Distinction: *Requirements Documents* vs *Work Items*

**For AI agents:** These are separate concepts that must not be confused.

| Concept                    | What It Is                                   | Examples                   |
| -------------------------- | -------------------------------------------- | -------------------------- |
| **Requirements Documents** | Vision artifacts (unbounded scope, no tests) | PRD, TRD                   |
| **Work Items**             | Sized implementation containers (testable)   | Capability, Feature, Story |

**Common mistakes:**

- ❌ "Capability TRD" — Nonsensical. TRD is a document type, Capability is a work item size.
- ❌ "Story TRD" — Impossible. TRD scope exceeds Story constraints.
- ✅ "Test Environment TRD" + "Capability: Test Environment" — Correct. TRD captures vision,
  Capability sizes the work.

A TRD might spawn 1 capability or 10. The document type says nothing about implementation size.

---

## Directory Layout

### Current State

```text
cloud-mirror/
├── AGENTS.md                           # AI agent entry point
├── dropbox-push.py                     # Working script (capability-27 reference)
├── pyproject.toml                      # Python project config (use with uv)
├── scripts/
│   ├── start-test-vm.sh                # Start Colima VM for ZFS testing
│   ├── setup-zfs-vm.sh                 # Install ZFS in Colima VM
│   └── create-test-pool.sh             # Create testpool in VM
├── tests/
│   ├── conftest.py                     # Pytest fixtures (ZFS, rclone mocks)
│   └── rclone-test.conf                # Mock rclone remote (local backend)
├── context/                            # Methodology and standards
│   ├── 1-structure.md                  # This file
│   ├── 2-workflow.md                   # Requirements → Decisions → Work Items
│   ├── 3-coding-standards.md           # Type annotations, style
│   ├── 4-testing-standards.md          # BDD methodology, test levels
│   ├── 5-commit-standards.md           # Conventional commits
│   └── templates/                      # Document templates
└── specs/doing/                        # Active work items
    ├── capability-10_colima-test-environment/
    ├── capability-27_dropbox-mirror-push/
    └── capability-54_dropbox-mirror-pull/
```

### Target State (cloud-mirror.py module)

```text
cloud-mirror/
├── cloud-mirror.py                             # Testable module (extracted from dropbox-push.py)
│   └── [or cloud_mirror/ package if complexity warrants]
├── dropbox-push.py                     # Legacy script (kept for reference)
├── tests/
│   ├── conftest.py                     # Shared fixtures
│   ├── unit/                           # Fast, no ZFS required
│   ├── integration/                    # Mocked rclone, requires Colima VM
│   └── e2e/                            # Full sync operations
└── specs/doing/                        # Work items (graduate tests here → tests/)
```

### Specs Structure (Work Items)

```text
specs/
├── requirements/                       # Vision documents (no size, no tests)
│   ├── {name}.prd.md                   # Product requirements
│   └── {name}.trd.md                   # Technical requirements
├── decisions/                          # Project-level architecture decisions
│   └── adr-{NNN}_{slug}.md             # Architecture decisions (how)
├── doing/                              # Active work items (sized, tested)
│   └── capability-{NN}_{slug}/
│       ├── {slug}.capability.md        # E2E test scenarios
│       ├── decisions/                  # Capability-scoped ADRs (optional)
│       │   └── adr-{NNN}_{slug}.md
│       └── feature-{NN}_{slug}/
│           ├── {slug}.feature.md       # Integration test scenarios
│           ├── decisions/              # Feature-scoped ADRs (optional)
│           │   └── adr-{NNN}_{slug}.md
│           └── story-{NN}_{slug}/
│               ├── {slug}.story.md     # Implementation notes
│               └── tests/              # Story tests (graduate when done)
├── backlog/                            # Future work
└── archive/                            # Completed capabilities
```

---

## Implicit Dependencies in Work Items

Work items do NOT explicitly reference each other. Dependencies are encoded in:

1. **Hierarchy**: Stories belong to Features, Features belong to Capabilities
2. **Numbering**: Lower numbers execute first (story-27 before story-44)
3. **Convention**: Story N assumes stories 1..N-1 within the same feature are complete

This eliminates redundancy and prevents stale cross-references. To understand what a story depends
on, look at its parent feature and lower-numbered siblings.

**Important**: A parent work item MUST NOT list its children. If an agent determines a requirement
is uncovered, it creates a new child—it does not annotate the parent. See
[2-workflow.md](./2-workflow.md#no-explicit-references-between-work-items).

---

## Smart Numbering: Binary Space Partitioning (BSP)

BSP assigns numbers to work items while maintaining the ability to insert new items without
renumbering. **Numbers encode execution order**—lower numbers complete before higher numbers within
the same parent, making explicit dependency declarations unnecessary.

### Range

Two-digit prefixes in range [10, 99] for work items at all hierarchy levels.

### Initial Distribution Formula

When inserting N items into range [10, 99]: `spacing = (99 - 10) // (N + 1)`

**Worked examples:**

- **2 items**: `spacing = 89 // 3 = 29` → positions `10 + 29 = 39`, `10 + 58 = 68`
- **3 items**: `spacing = 89 // 4 = 22` → positions 32, 54, 76
- **4 items**: `spacing = 89 // 5 = 17` → positions 27, 44, 61, 78

### Dynamic Insertion Between Items

```python
def insert_between(item_A, item_B):
    new_position = (item_A + item_B) // 2
    if new_position == item_A:
        raise RangeExhausted("Cannot subdivide further")
    return new_position
```

**Examples:**

- Insert between 39 and 68: `(39 + 68) // 2 = 53`
- Insert between 39 and 53: `(39 + 53) // 2 = 46`
- Insert between 39 and 46: `(39 + 46) // 2 = 42`

### Example Structure (from cloud-mirror)

```
capability-10_colima-test-environment/
├── colima-test-environment.capability.md
├── decisions/
│   └── adr-001_colima-zfs-environment.md
├── feature-32_colima-zfs-environment/
│   ├── colima-zfs-environment.feature.md
│   ├── story-32_colima-setup/
│   │   ├── colima-setup.story.md
│   │   └── tests/
│   ├── story-54_zfs-installation/
│   │   ├── zfs-installation.story.md
│   │   └── tests/
│   └── story-76_test-pool-creation/
│       ├── test-pool-creation.story.md
│       └── tests/
├── feature-54_pytest-fixtures/
└── feature-76_mock-rclone-remote/

capability-27_dropbox-mirror-push/
├── dropbox-push.capability.md          # References dropbox-push.py
├── feature-27_zfs-snapshot-operations/
├── feature-44_clone-tree-management/
├── feature-61_rclone-push-sync/
└── feature-78_push-cli/
```

---

## Test Lifecycle

Tests follow a three-phase lifecycle that enables multi-agent coordination without explicit
handover. See [2-workflow.md](./2-workflow.md#work-item-completion) for the complete completion
model.

### Development Phase

**Location**: `work-item/tests/`

- Tests co-located with work items during development
- Presence of test files indicates work in progress
- Tests should fail initially (RED), then pass (GREEN)

### Graduation Phase

**Location**: `tests/{unit,integration,e2e}/`

- Tests move to production test suites when work item is complete
- Graduated tests become regression protection
- Test names should clearly map to requirements for traceability

### Completion Marker

**File**: `work-item/tests/DONE.md`

- Created when work item is complete
- Lists graduated test locations as completion evidence
- Enables agents to verify completion without explicit handover

```
work-item/tests/
├── (no DONE.md)     # Work in progress
└── DONE.md          # Complete - references graduated tests
```

---

## Document Type Reference

| Document         | Layer        | Location                                      | Template                                             |
| ---------------- | ------------ | --------------------------------------------- | ---------------------------------------------------- |
| PRD              | Requirements | `specs/requirements/{name}.prd.md`            | TBD                                                  |
| TRD              | Requirements | `specs/requirements/{name}.trd.md`            | `templates/requirements/technical-change.trd.md`     |
| ADR (project)    | Decisions    | `specs/decisions/adr-{NNN}_{slug}.md`         | `templates/decisions/architectural-decision.adr.md`  |
| ADR (capability) | Decisions    | `capability-NN/decisions/adr-{NNN}_{slug}.md` | Same template                                        |
| ADR (feature)    | Decisions    | `feature-NN/decisions/adr-{NNN}_{slug}.md`    | Same template                                        |
| Capability       | Work Items   | `specs/doing/capability-{NN}_{slug}/`         | `templates/work-items/capability-name.capability.md` |
| Feature          | Work Items   | `specs/doing/.../feature-{NN}_{slug}/`        | `templates/work-items/feature-name.feature.md`       |
| Story            | Work Items   | `specs/doing/.../story-{NN}_{slug}/`          | `templates/work-items/story-name.story.md`           |
| DONE.md          | Completion   | `work-item/tests/DONE.md`                     | `templates/work-items/DONE.md`                       |
