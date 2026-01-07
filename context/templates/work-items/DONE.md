# Completion Evidence

> **Work Item**: [work-item-name]
> **Completed**: [YYYY-MM-DD]

This file marks the work item as complete and provides evidence that all requirements are met.

---

## Graduated Tests

Tests that prove functional requirements are met. These have been moved from `work-item/tests/` to
the production test suite.

| Requirement                       | Test Location                                         | Type        |
| --------------------------------- | ----------------------------------------------------- | ----------- |
| [Requirement text from work item] | `tests/unit/test_xxx.py::TestClass::test_name`        | Unit        |
| [Requirement text from work item] | `tests/integration/test_xxx.py::TestClass::test_name` | Integration |

### For Features and Capabilities

In addition to own tests, verify all children are complete:

```
# Feature: verify all story-*/tests/DONE.md exist
# Capability: verify all feature-*/tests/DONE.md exist
```

---

## Non-Functional Verification

Evidence that coding standards and ADR requirements are met.

| Standard                    | Evidence                                                 |
| --------------------------- | -------------------------------------------------------- |
| Type annotations            | All functions have type hints                            |
| Modern syntax (`T \| None`) | No use of `Optional[T]`                                  |
| Pydantic at boundaries      | `tests/integration/test_xxx.py::test_validates_response` |
| Dependency injection        | Constructor accepts optional dependencies                |
| Protocol compliance         | Implements `MediaAdapter` per ADR-54                     |

---

## Notes

[Any relevant notes about the implementation, deviations, or follow-up work identified]
