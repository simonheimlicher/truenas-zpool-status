# Story: Sample Files Fixture

## Functional Requirements

### FR1: Sample files fixture creates test files (FI3)

```gherkin
GIVEN a test using sample_files_in_tmp fixture
WHEN the test runs
THEN the temp directory contains:
  - file1.txt with known content
  - subdir/file2.txt with known content
  - symlink.txt pointing to file1.txt
```

## Files Created/Modified

1. `tests/conftest.py`: `sample_files_in_tmp` fixture
