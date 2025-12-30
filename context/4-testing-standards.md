# Testing Standards

## Core Principle: Test Behavior, Not Implementation

Tests describe **what the system does**, not how it does it internally.

## What NOT to Test

**Tests verify OUR code, not third-party tools or trivial infrastructure.**

### Don't Test Third-Party Tools

```python
# ❌ BAD - testing that rclone works as documented
def test_rclone_sync_copies_files():
    subprocess.run(["rclone", "sync", src, dest])
    assert dest_has_files()  # This tests rclone, not our code

# ❌ BAD - testing that ZFS commands work
def test_zfs_create_makes_dataset():
    subprocess.run(["zfs", "create", "testpool/data"])
    assert dataset_exists()  # This tests ZFS, not our code

# ✅ GOOD - testing OUR code that uses rclone
def test_sync_module_handles_rclone_failure():
    with mock_rclone_failure():
        result = our_sync_function(src, dest)
    assert result.error == "Sync failed"
```

### Don't Test Trivial Infrastructure

```python
# ❌ BAD - trivial, if config missing the real tests fail anyway
def test_config_file_exists():
    assert Path("rclone-test.conf").exists()

# ❌ BAD - testing fixture internals
def test_fixture_returns_path():
    assert test_remote.startswith("testremote:")

# ✅ GOOD - one smoke test that fails loudly and points fingers
def test_rclone_mock_remote_available():
    """Verify rclone infrastructure ready for Capability-27."""
    result = subprocess.run(["rclone", "--config", config, "listremotes"], ...)
    assert "testremote:" in result.stdout, (
        "rclone mock remote not available. "
        "See Feature-76 (mock-rclone-remote)."  # Points to responsible feature
    )
```

### Smoke Tests Should Point Fingers

When infrastructure fails, the error message must identify the responsible feature/capability so agents don't waste time debugging the wrong thing.

```python
# Good - tests behavior
def test_filter_returns_only_missing_movies():
    movies = [Movie(title="A", has_file=True), Movie(title="B", has_file=False)]
    result = apply_filter(movies, "!hasFile")
    assert result == [Movie(title="B", has_file=False)]

# Bad - tests implementation
def test_filter_calls_internal_method():
    with patch.object(Filter, '_check_predicate') as mock:
        apply_filter(movies, "!hasFile")
        mock.assert_called_once()  # Who cares?
```

---

## Test Structure: Given/When/Then

Every test should follow BDD structure:

```python
def test_sync_missing_movies_to_trakt():
    """
    Given: Radarr has movies, some without files
    When: Sync with filter !hasFile
    Then: Only missing movies appear in Trakt list
    """
    # Given
    radarr_movies = [
        Movie(title="Has File", has_file=True),
        Movie(title="Missing", has_file=False),
    ]

    # When
    result = sync_to_trakt(radarr_movies, filter="!hasFile")

    # Then
    assert result.added == ["Missing"]
    assert result.skipped == ["Has File"]
```

---

## Test Levels

### Unit Tests

**What**: Single function/class in isolation
**Speed**: < 1ms each
**Dependencies**: None (no I/O, no network, no filesystem)
**Location**: `tests/unit/`

```python
# Unit test - pure logic, no I/O
def test_parse_filter_hasFile():
    predicate = parse_filter("hasFile")
    assert predicate(Movie(has_file=True)) is True
    assert predicate(Movie(has_file=False)) is False
```

### Integration Tests

**What**: Component interactions with mocked boundaries
**Speed**: < 100ms each
**Dependencies**: Mocked (HTTP, filesystem, database)
**Location**: `tests/integration/`

```python
# Integration test - mocked HTTP
@respx.mock
def test_radarr_adapter_fetches_movies(respx_mock):
    respx_mock.get("/api/v3/movie").respond(json=[
        {"title": "Movie A", "year": 2024, "hasFile": True}
    ])

    adapter = RadarrAdapter(base_url="http://radarr", api_key="test")
    movies = adapter.read()

    assert len(movies) == 1
    assert movies[0].title == "Movie A"
```

### End-to-End Tests

**What**: Full user journey
**Speed**: < 10s each
**Dependencies**: Real or realistic (may use actual APIs in CI)
**Location**: `tests/e2e/` or capability `tests/` during development

```gherkin
# E2E test scenario
Feature: Sync Radarr to Trakt

  Scenario: Sync missing movies
    Given Radarr has movies with hasFile status
    When I run: imexport radarr trakt:missing --filter "!hasFile"
    Then Trakt list contains only movies without files
```

---

## Mocking Strategy

### Mock at Boundaries

Mock external systems (HTTP, filesystem, database), not internal code:

```python
# Good - mock the HTTP boundary
@respx.mock
def test_adapter_handles_api_error(respx_mock):
    respx_mock.get("/api/v3/movie").respond(status_code=500)

    adapter = RadarrAdapter(...)
    with pytest.raises(httpx.HTTPStatusError):
        adapter.read()

# Bad - mock internal implementation
def test_adapter_handles_api_error():
    with patch.object(RadarrAdapter, '_parse_response'):  # Don't mock internals
        ...
```

### Use respx for HTTP Mocking

```python
import respx
import httpx

@respx.mock
def test_with_decorator(respx_mock):
    respx_mock.get("https://api.example.com/movies").respond(json=[...])
    # test code

def test_with_context_manager():
    with respx.mock as mock:
        mock.get("https://api.example.com/movies").respond(json=[...])
        # test code
```

### Simulate Errors

```python
@respx.mock
def test_retry_on_connection_error(respx_mock):
    route = respx_mock.get("/api/v3/movie")
    route.side_effect = [
        httpx.ConnectError("Connection refused"),
        httpx.Response(200, json=[])
    ]

    adapter = RadarrAdapter(...)
    movies = adapter.read()  # Should succeed on retry

    assert route.call_count == 2
```

---

## Fixture Patterns

### Use pytest Fixtures for Setup

```python
@pytest.fixture
def sample_movies():
    return [
        Movie(title="Movie A", year=2024, has_file=True),
        Movie(title="Movie B", year=2023, has_file=False),
    ]

@pytest.fixture
def mock_radarr_api():
    with respx.mock(base_url="http://radarr:7878") as mock:
        yield mock

def test_filter_movies(sample_movies):
    result = apply_filter(sample_movies, "year>=2024")
    assert len(result) == 1
```

### Scope Fixtures Appropriately

```python
@pytest.fixture(scope="function")  # Default - new for each test
def mock_api():
    ...

@pytest.fixture(scope="module")    # Shared across tests in file
def expensive_setup():
    ...

@pytest.fixture(scope="session")   # Shared across all tests
def database_connection():
    ...
```

---

## Tests Define Done

### Capability Level

Capability is DONE when E2E test passes:

```python
def test_e2e_sync_radarr_to_trakt():
    """Capability: List Synchronisation"""
    # Full user journey test
    result = run_cli(["imexport", "radarr", "trakt:missing", "--filter", "!hasFile"])
    assert result.exit_code == 0
    assert "Added: 5" in result.output
```

### Feature Level

Feature is DONE when integration tests pass:

```python
def test_radarr_adapter_reads_all_movies():
    """Feature: Radarr Adapter"""
    # Component integration test
    ...

def test_radarr_adapter_handles_pagination():
    """Feature: Radarr Adapter"""
    ...
```

### Story Level

Story is DONE when it makes tests go RED → GREEN:

```python
# Before Story 1: Test fails (RED)
# After Story 1: Test passes (GREEN)
def test_media_item_has_required_fields():
    item = MediaItem(title="Movie", year=2024)
    assert item.title == "Movie"
    assert item.year == 2024
```

---

## Test Organization

```
tests/
├── conftest.py              # Shared fixtures
├── unit/
│   ├── test_models.py       # MediaItem, MediaIds
│   ├── test_filters.py      # Filter parsing and application
│   └── test_formatters.py   # CSV, JSON output
├── integration/
│   ├── test_radarr_adapter.py
│   ├── test_trakt_adapter.py
│   └── test_cli.py
└── e2e/
    └── test_sync_workflow.py
```

---

## Assertions

### Be Specific

```python
# Good - specific assertion
assert movies[0].title == "Expected Title"
assert len(movies) == 3

# Bad - vague assertion
assert movies  # What are we actually checking?
assert result is not None  # So what?
```

### Use pytest Features

```python
# Check exceptions
with pytest.raises(ValidationError) as exc_info:
    Movie(title="", year=-1)
assert "year" in str(exc_info.value)

# Approximate comparisons
assert result.duration == pytest.approx(1.5, rel=0.1)

# Parametrized tests
@pytest.mark.parametrize("filter_str,expected_count", [
    ("hasFile", 2),
    ("!hasFile", 3),
    ("year>=2024", 1),
])
def test_filter_variations(sample_movies, filter_str, expected_count):
    result = apply_filter(sample_movies, filter_str)
    assert len(result) == expected_count
```

---

## Speed Matters

### Keep Tests Fast

| Level       | Target  | Max   |
| ----------- | ------- | ----- |
| Unit        | < 1ms   | 10ms  |
| Integration | < 100ms | 500ms |
| E2E         | < 10s   | 60s   |

### Run Frequently

```bash
# Run unit tests constantly during development
uv run pytest tests/unit/ -x --ff

# Run integration tests before commit
uv run pytest tests/integration/

# Run E2E tests in CI or before merge
uv run pytest tests/e2e/
```

---

## Test Naming for Traceability

Test names must clearly map to requirements, enabling agents to determine which requirements are
covered without explicit cross-references. See [2-workflow.md](./2-workflow.md#work-item-completion)
for the completion model.

### Naming Convention

```python
# Pattern: test_{what}_{expected_behavior}
def test_csv_outputs_header_row():        # Requirement: "CSV has header row"
def test_filter_returns_only_missing():   # Requirement: "Filter returns missing movies"
def test_adapter_sends_api_key_header():  # Requirement: "API key sent in header"
```

### Class Organization

Group tests by the requirement area they cover:

```python
class TestCsvFormatter:
    """Tests for CSV output requirements."""

    def test_outputs_header_row(self): ...
    def test_outputs_data_rows(self): ...
    def test_handles_none_values(self): ...

class TestJsonFormatter:
    """Tests for JSON output requirements."""

    def test_outputs_valid_json(self): ...
    def test_ids_nested_object(self): ...
```

### Docstrings for Complex Mappings

When the mapping isn't obvious from the name, use a docstring:

```python
def test_media_ids_match_by_any_common_id(self):
    """
    Requirement: MediaIds.matches() returns True if ANY common ID matches.

    From ADR-54: "True if any common ID matches" enables cross-service
    matching when services have different ID coverage.
    """
```

### Anti-Patterns

```python
# Bad - unclear what requirement this covers
def test_it_works(): ...
def test_basic(): ...
def test_feature_1(): ...

# Bad - tests implementation, not requirement
def test_calls_internal_method(): ...
def test_uses_correct_class(): ...
```
