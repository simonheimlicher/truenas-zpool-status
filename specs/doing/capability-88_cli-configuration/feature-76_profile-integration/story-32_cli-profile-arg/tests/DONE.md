# Story 32: CLI Profile Argument - DONE

**Completion Date:** 2026-01-10
**Story:** Add --profile flag to CLI argument parser

## Implementation Summary

Modified `cloud_mirror/cli.py` to support profile-based configuration:

1. **Added --profile flag**:
   - Type: str (profile name)
   - Default: None
   - Help text: "Load settings from named profile in cloud-mirror.toml"

2. **Made positional arguments optional**:
   - Changed `source` to nargs="?", default=None
   - Changed `destination` to nargs="?", default=None
   - Enables profile-only invocation (no positionals required)

3. **Backward compatibility preserved**:
   - Existing `cloud-mirror source dest [options]` still works
   - Profile is optional, defaults to None
   - Mixed usage supported (positionals + --profile)

## Test Results

### Unit Tests (Level 1): 4 tests - All PASSING

**Location**: `tests/unit/cli/test_cli_profile_arg.py` (graduated)

Tests verify:

- --profile flag parsed correctly
- Optional positionals work (profile-only invocation)
- Positionals-only works (backward compatibility)
- Mixed usage (partial positionals + profile)

**Execution time**: 0.02s

### Graduated Tests

**Story unit tests** graduated from:

- `specs/.../story-32_cli-profile-arg/tests/test_cli_profile_arg.py`

**To**:

- `tests/unit/cli/test_cli_profile_arg.py`

## Quality Checks

- ✅ Type annotations: All correct
- ✅ Backward compatibility: Positionals-only still works
- ✅ Help text: Clear description of --profile flag
- ✅ No breaking changes: Existing invocations unchanged
- ✅ Type safety: mypy passes

## Files Modified

1. `cloud_mirror/cli.py` (modifications):
   - Lines 73-79: Made source optional (nargs="?", default=None)
   - Lines 81-87: Made destination optional (nargs="?", default=None)
   - Lines 89-96: Added --profile argument

## Verification Commands

```bash
# Test --profile flag
./cloud-mirror --help  # Should show --profile in options

# Test parsing
uv run --extra dev pytest tests/unit/cli/test_cli_profile_arg.py -v
```

## Completion Criteria Met

- [x] All Level 1 unit tests pass
- [x] No external dependencies (pure argparse testing)
- [x] BDD structure (GIVEN/WHEN/THEN) in all tests
- [x] --profile flag added to parser
- [x] source/destination made optional (nargs="?")
- [x] Backward compatibility preserved (positionals-only works)
- [x] Type annotations correct

## Notes

- Validation of source/destination happens in main(), not in the parser
- This allows profile to provide missing values before validation
- Story 54 (Profile Extraction) will implement the validation logic
- CLI args will override profile values (precedence handled in main())

## Integration Points

Ready for Story 54 (Profile Extraction):

- Parser now accepts --profile flag
- Positionals can be None (filled from profile)
- main() will validate source/dest after merge
