# ADR: Real Git Fixtures for Update Testing

## Problem

We need to test git-based self-update functionality. Should we mock git commands, use subprocess with real git against test fixtures, or use a git library (e.g., GitPython)?

## Options Considered

### Option 1: Mock git subprocess calls

Mock `subprocess.run()` to simulate git command outputs and return codes.

**Pros:**

- Fast (no actual git operations)
- No external dependencies
- Full control over edge cases

**Cons:**

- Tests don't verify actual git behavior
- Mock drift risk (mocks diverge from real git)
- Doesn't test real failure modes
- Complex to maintain (many subprocess calls to mock)

### Option 2: Real git with fixture repos in tmpdir

Create actual git repositories in `tmp_path` fixture, run real git commands via subprocess.

**Pros:**

- Tests actual git behavior (high confidence)
- Catches real git edge cases
- Simple implementation (reuse existing subprocess patterns)
- No mocking complexity

**Cons:**

- Slower than mocks (but still fast for git operations)
- Requires git installed (already required for development)

### Option 3: GitPython library

Use GitPython to manipulate git repos programmatically in tests.

**Pros:**

- Pythonic API for git operations
- Faster than subprocess

**Cons:**

- **New runtime dependency** (violates zero-dependency principle)
- Additional library to learn and maintain
- Subprocess pattern already established in codebase

## Decision

**We will use Option 2: Real git with fixture repos in tmpdir.**

## Rationale

cloud-mirror's testing philosophy (from `context/4-testing-standards.md`) emphasizes **real infrastructure over mocks**. The existing test suite already follows this pattern:

- ZFS tests run against actual ZFS in Colima VM (not mocked)
- rclone tests use actual rclone subprocess calls (not mocked)

Using real git aligns with this philosophy and provides the highest confidence that updates will work in production. Git operations are fast enough (milliseconds) that test performance is not a concern.

Since git is already required for development and cloud-mirror uses subprocess patterns throughout, adding real git fixtures is simpler than introducing mocks or new dependencies.

## Trade-offs Accepted

- **Test execution speed**: Real git operations add ~10-50ms per test vs instant mocks. This is acceptable because:
  - Git operations are inherently fast
  - Total test suite still runs in seconds
  - Confidence gain outweighs speed loss

- **Git installation requirement**: Tests require git installed on development machine. This is acceptable because:
  - Developers already have git (they cloned the repo)
  - CI/CD environments have git by default
  - Matches production environment (TrueNAS has git)

## Constraints

### Test Harness Requirements

Create `tests/fixtures/git_fixtures.py` with:

```python
@contextmanager
def with_git_repo(tmp_path: Path, commits: list[str] | None = None) -> GitRepo:
    """
    Context manager providing a temporary git repository.

    Args:
        tmp_path: pytest tmp_path fixture
        commits: List of commit messages to create (optional)

    Yields:
        GitRepo: Fixture with repo_path, helpers for git operations

    Example:
        with with_git_repo(tmp_path, commits=["Initial", "Second"]) as repo:
            repo.run_git("status")
            assert repo.current_commit() == commits[-1]
    """
```

### GitRepo Fixture API

The `GitRepo` dataclass must provide:

- `repo_path: Path` - Path to repository root
- `run_git(*args) -> subprocess.CompletedProcess` - Execute git command
- `current_commit() -> str` - Get current commit hash
- `current_branch() -> str` - Get current branch name
- `create_commit(message: str, files: dict[str, str]) -> str` - Create commit
- `create_tag(name: str) -> None` - Create annotated tag
- `checkout(ref: str) -> None` - Checkout branch/commit/tag

### Test Pattern

```python
def test_update_applies_new_commit(tmp_path):
    """Test that update applies when new commits exist."""
    with with_git_repo(tmp_path, commits=["v0.1.0"]) as repo:
        # Create "installed" version
        repo.create_tag("v0.1.0")
        initial_commit = repo.current_commit()

        # Simulate remote update
        repo.create_commit(
            "v0.2.0", {"cloud_mirror/__init__.py": '__version__ = "0.2.0"'}
        )
        repo.create_tag("v0.2.0")

        # Test update detection
        status = check_for_update(repo.repo_path)
        assert status.update_available
        assert status.current_version == "v0.1.0"
        assert status.remote_version == "v0.2.0"
```

### Fixture Lifecycle

1. **Setup**: Create bare repo, initialize, set user.name/user.email
2. **Populate**: Create commits/tags as specified
3. **Yield**: Provide GitRepo object for test
4. **Teardown**: tmp_path cleanup handled by pytest

### Integration with Existing Fixtures

Add to `tests/conftest.py`:

```python
from tests.fixtures.git_fixtures import with_git_repo


@pytest.fixture
def git_repo(tmp_path: Path) -> Generator[GitRepo, None, None]:
    """Provide a git repository fixture for tests."""
    with with_git_repo(tmp_path) as repo:
        yield repo
```

This allows tests to use `git_repo` as a standard pytest fixture.
