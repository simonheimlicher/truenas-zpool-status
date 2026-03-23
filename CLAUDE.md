# CLAUDE.md - zpool-status

## Critical Rules

- ⚠️ **NEVER write code without invoking a skill first** - See skill table below
- ⚠️ **NEVER manually navigate `spx/` hierarchy** - Use spec-tree skills
- ⚠️ **ALWAYS read CLAUDE.md in subdirectories** - When working with files in `spx/`, or any other directory, read that directory's CLAUDE.md FIRST if it exists
- ⚠️ **Skills are ALWAYS authoritative over existing files** - When a skill prescribes a structure, follow the skill — not patterns found in existing spec files. Existing files may contain non-standard sections added before skills existed.
- ⚠️ **NEVER maintain backward compatibility** - When rewriting a module, replace it entirely. No legacy aliases, no re-exports, no shims. Update all imports across the codebase.
- ⚠️ **NEVER reference specs or decisions from code** - No `ADR-001`, `capability-10`, or similar in Python comments or docstrings. Specs are the source of truth; code should not reference them.
- ⚠️ **NEVER edit `pyproject.toml` for dependency changes** - Use `uv add`/`uv remove` — they update pyproject.toml, lockfile, and venv atomically
- ✅ **Always use `just test`** - Never bare pytest (just loads environment correctly)
- ✅ **Always use `uv`** - NEVER use pip
- ✅ **`just check-full` MUST PASS** before any work is considered complete
- ✅ **If you have the tool `AskUserQuestion`, always use it**

### `just check-full` MUST PASS

**`just check-full` MUST PASS before any work is considered complete.**

This is non-negotiable. No exceptions. No cheating.

**What counts as cheating:**

- Adding `# noqa`, `# type: ignore`, or `# ruff: noqa` to silence errors
- Disabling lint rules in `pyproject.toml` to make errors disappear
- Excluding files from checking to hide failures
- Marking tests as `@pytest.mark.skip` to avoid fixing them
- Any other trick to make `just check-full` pass without actually fixing issues

**If `just check-full` fails, you MUST fix the underlying issues.**

### Zero Tolerance Applies to ALL Executable Code

| Category              | Examples                  | Same Standard                  |
| --------------------- | ------------------------- | ------------------------------ |
| **Package modules**   | `zpool_status/*.py`       | ✅ Full type checking, linting |
| **Unit tests**        | `spx/**/*test*.py`        | ✅ Full type checking, linting |
| **Integration tests** | `spx/**/*.integration.py` | ✅ Full type checking, linting |
| **E2E tests**         | `spx/**/*.e2e.py`         | ✅ Full type checking, linting |
| **Test fixtures**     | `spx/**/conftest.py`      | ✅ Full type checking, linting |

---

## What Is This Project?

**zpool-status** provides enhanced ZFS pool status output for TrueNAS SCALE, augmenting `zpool status` with disk identification (model, serial number) via `smartctl`.

**Target Environment**: TrueNAS SCALE (Linux, Python 3.11, native ZFS, smartmontools pre-installed)

## Project Structure

```
zpool-status/
├── CLAUDE.md              # This file
├── justfile               # Task runner (just test, just check-full, etc.)
├── pyproject.toml         # Project config (use with uv)
├── zpool_status/          # Main package
│   ├── __init__.py
│   ├── __main__.py        # python -m zpool_status
│   ├── main.py            # CLI entry point (zpstat command)
│   └── status.py          # Core: parse zpool status, enrich with smartctl
├── tests/                 # Environment verification & shared fixtures only
│   └── test_status.py     # Unit tests (mocked subprocess calls)
└── spx/                   # Spec tree (work items, decisions, tests)
```

## Usage

```bash
# On TrueNAS SCALE:
zpstat status [pool]    # Enhanced zpool status with MODEL and SERIAL columns
```

## Key Design Decisions

- **smartctl for disk info**: Most reliable source on TrueNAS SCALE (smartmontools pre-installed)
- **No external dependencies**: stdlib only — runs on TrueNAS's system Python without pip install
- **Zero ZFS required for tests**: All subprocess calls are mocked, tests run anywhere

---

## MANDATORY: Use Skills for ALL Work

**THIS IS NON-NEGOTIABLE.** Before performing ANY task — writing code, answering questions, or anything else — you MUST invoke the appropriate skill.

### Required Skills for Questions

| User asks about...                       | Skill to Invoke                          |
| ---------------------------------------- | ---------------------------------------- |
| Testing, test patterns, or test fixtures | `python:testing-python` + `test:testing` |
| Code, design, or implementation          | `python:reviewing-python`                |
| Specs or spx/ structure                  | `spec-tree:understanding`                |
| Architecture or design decisions         | `python:architecting-python`             |

### Required Skills for Tasks

| User asks to...                                               | Skill to Invoke                          |
| ------------------------------------------------------------- | ---------------------------------------- |
| Write tests                                                   | `python:testing-python` + `test:testing` |
| Write Python code (ONLY AFTER tests exist — TDD is MANDATORY) | `python:coding-python`                   |
| Review code                                                   | `python:reviewing-python`                |
| Make architecture decisions                                   | `python:architecting-python`             |
| Review ADRs                                                   | `python:reviewing-python-architecture`   |
| Commit                                                        | `spec-tree:committing-changes`           |
| Resume work (after /pickup)                                   | `spec-tree:understanding`                |
| Navigate or query spec tree                                   | `spec-tree:contextualizing`              |
| Create/modify spec tree nodes                                 | `spec-tree:authoring`                    |
| Break down work items                                         | `spec-tree:decomposing`                  |

### `.claude/` Directory

The `.claude/` directory is **part of the project** (version-controlled), not user-local config.

| Path                          | Purpose                                                     | Tracked |
| ----------------------------- | ----------------------------------------------------------- | ------- |
| `.claude/settings.json`       | Project-wide Claude Code settings (shared across all users) | Yes     |
| `.claude/settings.local.json` | User-local overrides (gitignored)                           | No      |
| `.claude/skills/`             | Skills — authoritative templates, workflows, conventions    | Yes     |

### Skills Are Authoritative

The skills in `.claude/skills/` are the **single source of truth** for all `spx/` operations. Never infer framework conventions from existing spec files; existing files may contain non-standard patterns that predate the skills.

---

## Running Commands

```bash
# Run tests
just test                        # All tests
just test spx/some-capability/   # Tests under a specific path
just test "-x --ff"              # Stop on first failure

# Formatting
just fmt                         # Format all code
just fmt-check                   # Check formatting without modifying

# Type checking and linting
just typecheck
just lint
just check                       # Fast core checks (lint + typecheck)
just check-full                  # Full checks (lint + typecheck + all tests)
```

**Important**: Always use `just test` instead of bare `pytest` — it ensures environment variables are loaded and uv is used correctly.

---

## Commit Workflow

**ALWAYS format code before committing.**

```bash
# Before committing:
just fmt              # 1. Format code (REQUIRED)
just lint             # 2. Check for lint errors
just typecheck        # 3. Check types
just test <path>      # 4. Run relevant tests

# Or use the combined command:
just check-full       # Runs everything
```

---

## Centralized Tool Configuration

### All configuration lives in `pyproject.toml`

```toml
[tool.mypy]
strict = true

[tool.ruff.lint]
select = ["B", "S", "PT", "T20"]

[tool.pytest.ini_options]
testpaths = ["tests", "spx"]
```

### NEVER edit `pyproject.toml` for dependency changes

```bash
# ❌ WRONG - manual edit misses lockfile and venv sync
# Editing dependencies by hand

# ✅ CORRECT - uv manages everything
uv add --group dev "new-package>=1.0"    # Add dev dependency
uv add "click>=8.0"                      # Add runtime dependency
uv remove --group dev old-package        # Remove dev dependency
```

Tool **configuration** sections (`[tool.mypy]`, `[tool.ruff]`, `[tool.pytest.ini_options]`) are fine to edit directly — those are not managed by `uv`.

---

## Test Location

Tests are **co-located** with specs permanently.

| Scope      | Test Location                    |
| ---------- | -------------------------------- |
| Story      | `spx/.../story-NN_slug/tests/`   |
| Feature    | `spx/.../feature-NN_slug/tests/` |
| Capability | `spx/capability-NN_slug/tests/`  |

**No graduation.** Tests never move to a top-level `tests/` directory. The `tests/` directory at project root is for environment verification and shared fixtures only.

---

## Enforcement: STOP Triggers

If you find yourself doing any of these, **STOP immediately**:

- Accessing files in `spx/` without reading that directory's CLAUDE.md → STOP, read it first
- Writing code without invoking a skill → STOP, invoke skill
- Writing tests without invoking `testing-python` → STOP, invoke skill
- Making architecture decisions without `architecting-python` → STOP, invoke skill
- Committing without invoking `spec-tree:committing-changes` → STOP, invoke skill
- Moving tests to the top-level `tests/` directory → STOP, tests stay co-located in `spx/`
- Uncertain about requirements → STOP, use `AskUserQuestion`
- `just check-full` fails → STOP, fix the issues before proceeding
- Tempted to add `# noqa` or `# type: ignore` → STOP, fix the actual problem
- Keeping old class names or re-exports for backward compatibility → STOP, replace entirely
- Adding spec references (ADR-001, etc.) to Python comments → STOP, code must not reference specs
- Editing `pyproject.toml` dependencies by hand → STOP, use `uv add`/`uv remove`
- Using an Agent to create, edit, or write ANY file → STOP, agents are read-only research tools

**Load the skill FIRST, then proceed.**

---

## Always Use AskUserQuestion

**Always use the `AskUserQuestion` tool to obtain guidance from the user**: discover context, obtain rationale, and support the user in making the right call by asking critical questions before blindly following requests.

**NEVER ask the user any questions without using the `AskUserQuestion` tool.**
