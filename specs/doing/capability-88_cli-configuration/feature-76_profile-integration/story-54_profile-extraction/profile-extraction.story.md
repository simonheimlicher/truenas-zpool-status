# Story: Profile Extraction and Config Flow

## Functional Requirements

### FR1: Load config when --profile provided

```gherkin
GIVEN user provides --profile NAME
WHEN main() executes
THEN load_config() called to read cloud-mirror.toml
AND config structure retrieved with defaults and profiles
```

### FR2: Extract and validate profile

```gherkin
GIVEN config loaded with profiles
WHEN extracting profile by name
THEN verify profile exists in config["profiles"]
AND return clear error if profile not found
AND list available profiles in error message
```

### FR3: Merge config with precedence: defaults → profile → CLI

```gherkin
GIVEN defaults from config, profile settings, and CLI args
WHEN merge_config() called
THEN CLI args override profile values
AND profile values override defaults
AND merged config contains all settings
```

### FR4: Defer direction detection until after merging

```gherkin
GIVEN profile can provide source/destination
WHEN --profile used without positionals
THEN extract source/dest from merged config (not parsed args)
AND detect direction AFTER merge completes
AND validate both source/dest present after merge
```

### FR5: Preserve backward compatibility

```gherkin
GIVEN no --profile flag
WHEN traditional invocation used
THEN config loading skipped
AND direction detection uses parsed positionals
AND existing behavior unchanged
```

##Testing Strategy

Stories require **Level 1** to prove core logic works.

### Level Assignment

| Component          | Level | Justification                                   |
| ------------------ | ----- | ----------------------------------------------- |
| Profile extraction | 1     | Dict operations, no I/O                         |
| Config merging     | 1     | Pure merge logic (already tested in Feature 32) |
| Validation logic   | 1     | String checks, no external deps                 |

## Completion Criteria

- [ ] All unit tests pass
- [ ] main.py modified with config flow
- [ ] Direction detection after merge
- [ ] Backward compatibility preserved
- [ ] Clear error messages
