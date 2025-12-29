# Commit and Deployment Standards

## Deployment Gate Requirements

**Every commit and story deployment must pass ALL of these criteria before deployment:**

### Automated Checks (All Must Pass)

- [ ] **`uv run --with pytest pytest tests/ specs/`** shows **0** failed tests
- [ ] **`uv run --with mypy mypy cloud-mirror.py`** shows **0** type errors (once type hints added)
- [ ] **`uv run --with ruff ruff check cloud-mirror.py`** shows **0** errors (warnings acceptable)
- [ ] **`python cloud-mirror.py --help`** succeeds (CLI smoke test)

### Manual Verification Requirements

- [ ] **Story Value Delivered**: Story delivers the promised technical value as defined in requirements
- [ ] **No Breaking Changes**: Existing functionality works as before (regression testing)
- [ ] **Documentation Updated**: If new capabilities introduced, documentation reflects changes
- [ ] **Feature Status Current**: `feature/tests/status.yaml` updated with latest test outcomes (when applicable)

### Story-Level Deployment Criteria

For story-level deployments, additionally verify:

- [ ] **Story Completion**: All acceptance criteria met
- [ ] **Independent Deployment**: Story can be deployed without dependencies on incomplete stories
- [ ] **Rollback Safety**: Changes can be safely reverted if issues arise

---

## Pre-Commit Verification Protocol

**Before creating ANY commit, follow this exact sequence:**

### Step 1: Selective Staging (NEVER use `git add .`)

```bash
# ❌ NEVER do this - stages everything including incomplete work
git add .

# ✅ ALWAYS do this - stage only files related to your specific change
git add scripts/start-test-vm.sh specs/doing/capability-10_colima-test-environment/feature-32_colima-zfs-environment/story-32_colima-setup/
```

**Staging Rules:**
- [ ] **One Story Per Commit**: Only stage files related to the single story/issue being fixed
- [ ] **Review Untracked Files**: Run `git status` and consciously decide about each `??` file
- [ ] **Exclude Experimental Work**: Never stage files from other stories unless explicitly related
- [ ] **Avoid Wildcards**: Use explicit file paths, not `*.py` or directory names

### Step 2: Pre-Commit Diff Review

```bash
# Review exactly what will be committed
git diff --cached

# Verify file list matches your intent
git diff --cached --name-only
```

**Review Checklist:**
- [ ] **File Count Reasonable**: Does the number of files match the scope of your fix?
- [ ] **No Surprise Files**: Are there files you didn't intend to modify?
- [ ] **No Unrelated Changes**: Are all changes related to the single issue being fixed?
- [ ] **No Debug Code**: No debug print statements, temporary comments, or experimental code?

### Step 3: Atomic Commit Verification

- [ ] **Single Purpose**: Does this commit do exactly one thing?
- [ ] **Story Boundary**: Are all changes related to the same story/issue?
- [ ] **Independent**: Could this commit be reverted without breaking other features?
- [ ] **Complete**: Does this commit include everything needed for the fix to work?

### Red Flags - DO NOT COMMIT IF:

- More than 10 files changed for a simple bug fix
- Files from multiple story directories included
- New files (`??`) that weren't explicitly intended
- Changes in unrelated modules or domains
- Experimental/incomplete implementations mixed with stable fixes

---

## Conventional Commits Standard

We follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) with types appropriate for CLI tools.

## Commit Types

| Type         | Purpose                                        | SemVer Impact | Examples                                                      |
| ------------ | ---------------------------------------------- | ------------- | ------------------------------------------------------------- |
| **feat**     | New capability                                 | MINOR         | `feat: add clone tree management for snapshot sync`           |
| **fix**      | Bug fix                                        | PATCH         | `fix: handle unmounted dataset in recursive snapshot`         |
| **docs**     | Documentation changes                          | PATCH         | `docs: update CLI usage examples`                             |
| **style**    | Code formatting (no logic change)              | PATCH         | `style: apply black formatting to sync module`                |
| **refactor** | Code restructure, architecture improvements    | PATCH         | `refactor: extract ZFS operations into separate module`       |
| **perf**     | Performance improvements                       | PATCH         | `perf: batch rclone operations to reduce API calls`           |
| **test**     | Add or modify tests                            | PATCH         | `test: add integration tests for Colima VM setup`             |
| **ci**       | CI/CD pipeline changes                         | PATCH         | `ci: add automated test workflow`                             |
| **build**    | Build system or dependencies                   | PATCH         | `build: add pytest dependency to pyproject.toml`              |
| **revert**   | Revert previous commit                         | PATCH         | `revert: "feat: add experimental sync mode"`                  |
| **ctx**      | Context, workflow, AI/human collaboration      | PATCH         | `ctx: add BSP numbering guidance to structure doc`            |

## Type Selection Guidelines

### Use `ctx:` for

- Context documentation (`context/*.md` changes)
- Work item structure and templates
- Workflow and process documentation
- AI/human collaboration patterns
- ADR, TRD, capability/feature/story templates

### Use `feat:` for

- New sync operations (push, pull)
- New CLI options or commands
- ZFS snapshot/clone functionality
- rclone integration features

### Use `fix:` for

- ZFS command handling issues
- Clone cleanup failures
- rclone sync errors
- CLI argument validation fixes

### Use `refactor:` for

- Extracting modules from dropbox-push.py → cloud-mirror.py
- Improving code organization
- Technical debt reduction

### Use `docs:` for

- README updates
- CLAUDE.md updates
- Context documentation
- Inline code documentation

### Use `test:` for

- Unit test additions
- Integration test fixtures
- BDD feature files

### Avoid Completely

- `chore:` - Everything we do has purpose and value

## Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**CRITICAL:** DO NOT INCLUDE ANY ATTRIBUTION!

## Breaking Changes

Any type can include:

- '!' suffix: `feat!: change CLI syntax to positional arguments`
- 'BREAKING CHANGE:' footer for major version bump

## Scope Usage Guidelines

### When to Use Scopes

- **Component-specific changes**: `feat(zfs): add recursive snapshot creation`
- **Module changes**: `fix(rclone): handle rate limiting`
- **Script changes**: `feat(vm): add ZFS installation script`

### When to Omit Scopes

- **Single-function changes**: `fix: handle empty dataset list`
- **Cross-cutting changes**: `refactor: consolidate error handling`
- **Simple, obvious changes**: `docs: update installation guide`

### Common Scopes

| Scope      | Purpose                                           |
| ---------- | ------------------------------------------------- |
| `zfs`      | ZFS snapshot, clone, dataset operations           |
| `rclone`   | rclone sync, remote configuration                 |
| `vm`       | Colima VM setup and management scripts            |
| `clone`    | Clone tree creation and cleanup                   |
| `cli`      | CLI argument parsing, direction detection         |
| `sync`     | Core sync module (cloud-mirror.py)                        |
| `context`  | Context documentation (`context/*.md`)            |
| `template` | Work item templates (`context/templates/`)        |
| `spec`     | Specifications (`specs/` work items, ADRs)        |

## Quick Reference Decision Tree

```
Is this context/workflow documentation? → ctx:
Is this a new capability? → feat:
Is this fixing a bug? → fix:
Is this improving performance? → perf:
Is this code reorganization? → refactor:
Is this build/dependencies? → build:
Is this code documentation? → docs:
Is this testing infrastructure? → test:
```

## Example Commits

### Good Examples

```bash
# Feature with clear value
feat(zfs): add recursive snapshot creation with timestamp naming

# Bug fix with context
fix(clone): handle unmounted child datasets during clone tree build

Some child datasets may be unmounted. Now checks mount status
before attempting to access .zfs/snapshot directory.

# Refactor with justification
refactor: extract ZFS operations from dropbox-push.py

Prepares codebase for testable cloud-mirror.py module by isolating
ZFS-specific logic into functions.

# Context/workflow update
ctx: add BSP numbering examples to structure documentation

Restore detailed formula and worked examples for AI agents
to correctly assign work item numbers.

# Template update
ctx(template): simplify story template, remove redundant ADR references

# Test infrastructure
test(vm): add Colima VM setup integration tests

Verify VM starts, ZFS installs, and testpool creates correctly.
```

### Poor Examples

```bash
# ❌ Too vague
fix: bug fixes

# ❌ Multiple unrelated changes
feat: add clone tree and fix rclone and update docs

# ❌ Contains attribution
feat: add pull support (implemented by John)

# ❌ Not atomic
refactor: various improvements
```

## Commit Message Best Practices

1. **Subject Line** (50 characters or less)
   - Use imperative mood: "add feature" not "added feature"
   - Don't end with period
   - Be specific and descriptive

2. **Body** (optional, wrap at 72 characters)
   - Explain WHAT and WHY, not HOW
   - Reference relevant issues or requirements
   - Include context for reviewers

3. **Footer** (optional)
   - Reference work items: `Refs: capability-54/feature-32/story-27`
   - Breaking changes: `BREAKING CHANGE: description`
   - Closes issues: `Closes #123`

## Pre-Deployment Checklist

Before merging to main:

- [ ] All automated checks pass
- [ ] Manual verification complete
- [ ] Test cases cover new functionality
- [ ] Error scenarios tested
- [ ] Documentation updated
- [ ] Commit message follows standards
