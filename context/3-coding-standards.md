# Coding Standards

## Type Safety

### Annotations Required

All functions, methods, and class attributes must have type annotations:

```python
# Good
def fetch_movies(base_url: str, api_key: str) -> list[Movie]:
    ...

# Bad - missing annotations
def fetch_movies(base_url, api_key):
    ...
```

### Modern Syntax

- Use `T | None` not `Optional[T]`
- Use `list[T]` not `List[T]` (Python 3.9+)
- Use `dict[K, V]` not `Dict[K, V]`

```python
# Good
def get_movie(id: int) -> Movie | None:
    ...

# Bad - old syntax
from typing import Optional
def get_movie(id: int) -> Optional[Movie]:
    ...
```

### Protocol for Interfaces

Use `typing.Protocol` for interfaces, not `abc.ABC`:

```python
from typing import Protocol

class MediaAdapter(Protocol):
    """Any class with these methods satisfies the interface."""

    def read(self) -> list[MediaItem]: ...
    def write(self, items: list[MediaItem]) -> WriteResult: ...
```

**Why Protocol over ABC:**

- Structural subtyping (duck typing) - no inheritance required
- Works with third-party code you don't control
- Static type checking with mypy

---

## Data Validation

### Validate at Boundaries

External data (API responses, user input, file contents) must be validated before use:

```python
from pydantic import BaseModel, TypeAdapter

class Movie(BaseModel):
    title: str
    year: int
    tmdb_id: int | None = None

# Validate API response
response = client.get("/api/v3/movie")
movies = TypeAdapter(list[Movie]).validate_python(response.json())
```

### Use Pydantic for External Data

- `BaseModel` for single objects
- `TypeAdapter` for collections
- Field validators for domain constraints

```python
from pydantic import BaseModel, field_validator

class Movie(BaseModel):
    title: str
    year: int

    @field_validator('year')
    @classmethod
    def year_reasonable(cls, v: int) -> int:
        if v < 1888 or v > 2100:
            raise ValueError('year must be between 1888 and 2100')
        return v
```

### Fail Fast

Invalid data should raise exceptions immediately, not propagate silently:

```python
# Good - fails immediately on bad data
movie = Movie.model_validate(data)  # Raises ValidationError

# Bad - silently accepts bad data
movie = Movie(**data)  # No validation
```

---

## Dependency Injection

### Accept Dependencies as Parameters

Classes should accept their dependencies, not create them:

```python
# Good - injectable
class RadarrAdapter:
    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client()

# Bad - hard-coded dependency
class RadarrAdapter:
    def __init__(self):
        self._client = httpx.Client()  # Can't inject for testing
```

### Provide Sensible Defaults

Production code should work without explicit injection:

```python
# Works in production (uses default)
adapter = RadarrAdapter(base_url="http://radarr:7878", api_key="xxx")

# Works in tests (inject mock)
adapter = RadarrAdapter(base_url="...", api_key="...", client=mock_client)
```

---

## Error Handling

### Let Exceptions Propagate

Don't catch exceptions unless you can meaningfully handle them:

```python
# Good - let caller handle
def fetch_movies(self) -> list[Movie]:
    response = self._client.get("/api/v3/movie")
    response.raise_for_status()  # Propagates HTTPStatusError
    return self._parse_response(response)

# Bad - swallows errors
def fetch_movies(self) -> list[Movie]:
    try:
        response = self._client.get("/api/v3/movie")
        return self._parse_response(response)
    except Exception:
        return []  # Silent failure, caller has no idea
```

### Use Specific Exceptions

Catch specific exception types, not `Exception`:

```python
# Good
try:
    response = client.get(url)
except httpx.ConnectError:
    logger.warning("Connection failed, will retry")
    raise
except httpx.TimeoutException:
    logger.warning("Request timed out")
    raise

# Bad
try:
    response = client.get(url)
except Exception as e:  # Too broad
    logger.error(f"Something went wrong: {e}")
```

---

## Code Organization

### Single Responsibility

Each module/class should have one reason to change:

```python
# Good - separate concerns
class RadarrClient:       # HTTP interaction
class MovieParser:        # Data transformation
class RadarrAdapter:      # Orchestration

# Bad - mixed concerns
class RadarrAdapter:
    def fetch_and_parse_and_filter_and_export(self): ...
```

### Explicit Over Implicit

Make dependencies and behavior explicit:

```python
# Good - explicit configuration
adapter = RadarrAdapter(
    base_url="http://radarr:7878",
    api_key=os.environ["RADARR_API_KEY"],
    timeout=30.0
)

# Bad - hidden configuration
adapter = RadarrAdapter()  # Where does config come from?
```

---

## Naming Conventions

| Item         | Convention    | Example                   |
| ------------ | ------------- | ------------------------- |
| Modules      | `snake_case`  | `radarr_adapter.py`       |
| Classes      | `PascalCase`  | `RadarrAdapter`           |
| Functions    | `snake_case`  | `fetch_movies()`          |
| Constants    | `UPPER_SNAKE` | `DEFAULT_TIMEOUT`         |
| Type aliases | `PascalCase`  | `MovieList = list[Movie]` |

### Naming Guidelines

- Name functions after what they DO: `fetch_movies`, `parse_response`
- Name classes after what they ARE: `RadarrAdapter`, `MovieFilter`
- Name booleans as questions: `has_file`, `is_monitored`
- Avoid abbreviations unless universally understood: `id`, `url`, `api`
