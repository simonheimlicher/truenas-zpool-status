# Story: Mock Remote Configuration

## Functional Requirements

### FR1: Mock rclone remote available for testing

```gherkin
GIVEN tests/rclone-test.conf exists with testremote configured
WHEN Capability-27 tests run
THEN they can use testremote: without network access to Dropbox
```

## Files Created/Modified

1. `tests/rclone-test.conf`: rclone configuration with local backend
2. `tests/conftest.py`: `test_remote`, `rclone_config` fixtures
