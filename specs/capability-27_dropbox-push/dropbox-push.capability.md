# Capability: Radarr to Trakt List Sync

## Summary

## Scope

### In Scope

### Out of Scope

## Integration Test Scenarios

### INT-1: CSV export contains required fields

```gherkin
```

### INT-2: JSON export is valid JSON

```gherkin
```

### INT-3: CLI writes to file

```gherkin
```

### INT-4: CLI writes to stdout

```gherkin
```

## CLI Design

```bash
# New CLI allows pulling from Dropbox
./cloud-mirror.py dropbox:Books/ebooks apps/books/ebooks
```

## Definition of Done

- [ ] Unit tests pass
- [ ] New CLI allows pulling from Dropbox
