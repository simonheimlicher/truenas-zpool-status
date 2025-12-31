# ADR-001: rclone Push Sync Testing Strategy

## Problem

Feature-61 (rclone Push Sync) currently has ZERO test coverage. The existing `rclone-test.conf` uses `type=local` which provides no confidence that the code works with real Dropbox.

What testing levels are required for each component, and what infrastructure is needed?

## Options Considered

### Option 1: Mock Everything

Use `@patch` to mock all subprocess calls. Fast, no infrastructure needed.

### Option 2: Local Backend Only (Level 2)

Test with rclone's `type=local` backend in Colima VM. Proves rclone commands work but not Dropbox-specific behaviors.

### Option 3: 4-Level Testing Strategy

Test each component at the minimum level that provides real confidence:

- Level 1: Pure logic (command building, error parsing)
- Level 2: Real rclone with local backend (VM)
- Level 3: Real Dropbox test account (internet)
- Level 4: Production pre-flight checks

## Decision

**We will use Option 3: 4-Level Testing Strategy.**

## Rationale

Mocking provides ZERO confidence—it tests whether our mocks are correct, not whether the code works. The current `type=local` backend proves rclone runs but cannot verify:

- Dropbox OAuth authentication works
- Rate limiting is handled correctly
- Dropbox-specific behaviors (mtime, symlinks, .rclonelink)
- Network error handling

Each testing level adds dependencies but also adds confidence that lower levels cannot provide.

## Testing Strategy

### Level Assignments

| Component | Level | Justification |
|-----------|-------|---------------|
| `build_rclone_command()` | 1 (Unit) | Pure function, no I/O |
| `parse_rclone_error()` | 1 (Unit) | Pure parsing logic |
| `parse_rclone_output()` (verbosity) | 1 (Unit) | Pure string filtering |
| `get_version_backup_path()` | 1 (Unit) | Pure path manipulation |
| Basic sync to local remote | 2 (VM) | Need real rclone, local backend sufficient |
| Symlink → .rclonelink conversion | 2 (VM) | rclone behavior, local backend works |
| Directory structure preservation | 2 (VM) | Filesystem behavior |
| Version backup file operations | 2 (VM) | rclone --backup-dir, local backend works |
| **Dropbox OAuth authentication** | **3 (Internet)** | REQUIRES real Dropbox |
| **Rate limit handling (429 errors)** | **3 (Internet)** | REQUIRES real Dropbox API |
| **Dropbox mtime preservation** | **3 (Internet)** | Dropbox-specific behavior |
| **Real sync verification** | **3 (Internet)** | End-to-end confidence |
| Production config works | 4 (Preflight) | Environment-specific |
| Remote is accessible | 4 (Preflight) | Runtime verification |

### Escalation Rationale

**Level 1 → 2:**
> "Unit tests prove command building logic is correct, but cannot verify rclone actually accepts our commands or syncs files correctly."

**Level 2 → 3:**
> "VM tests prove rclone syncs files with local backend, but cannot verify:
>
> - OAuth token refresh works
> - Dropbox rate limits (too_many_write_operations) are handled
> - `--tpslimit 12` actually prevents rate errors
> - Dropbox's mtime precision (1-second resolution) is handled
> - Real network latency and timeout handling"

**Level 3 → 4:**
> "Test account works in CI, but production may have:
>
> - Different rclone config location
> - Different Dropbox account with different permissions
> - Different network configuration"

### Level 3 Infrastructure Requirements

**MANDATORY for capability-27 completion:**

1. **Dedicated Dropbox Test Account**
   - Create App Folder with limited scope (not full Dropbox access)
   - Document: "Dropbox > App Console > Create App > Scoped access > App folder"
   - Test folder: `Apps/cloud-mirror-test/`

2. **Credentials Management**
   - Environment variable: `DROPBOX_TEST_TOKEN`
   - CI secret: `secrets.DROPBOX_TEST_TOKEN`
   - Never commit tokens
   - rclone config generated at runtime:

     ```ini
     [dropbox-test]
     type = dropbox
     token = ${DROPBOX_TEST_TOKEN}
     ```

3. **Test Isolation**
   - Each test run creates unique folder: `test_{uuid}/`
   - Fixture cleans up via `rclone purge` in teardown
   - No shared state between tests

4. **pytest Markers**

   ```python
   @pytest.mark.internet_required  # Level 3
   @pytest.mark.flaky(reruns=3)    # Handle transient failures
   ```

### Behaviors That MUST Be Tested at Level 3

| Behavior | Why Level 2 Is Insufficient |
|----------|----------------------------|
| OAuth authentication | Local backend has no OAuth |
| Token refresh on expiry | Local backend never expires |
| Rate limit retry (429 → backoff → retry) | Local backend never rate limits |
| `--tpslimit 12` effectiveness | Only real API rate limits |
| Dropbox-specific error messages | Local errors differ from API errors |
| Network timeout handling | No network in local backend |
| Idempotent sync verification | Need real checksums from Dropbox |

### Level 3 Test Cases (Required)

```python
@pytest.mark.internet_required
class TestDropboxSync:
    """MANDATORY Level 3 tests for real Dropbox."""

    def test_files_sync_to_dropbox(self, dropbox_test_folder):
        """FI1 at Level 3: Verify files actually appear on Dropbox."""

    def test_symlinks_become_rclonelink_on_dropbox(self, dropbox_test_folder):
        """FI2 at Level 3: Verify .rclonelink works on Dropbox."""

    def test_version_backup_works_on_dropbox(self, dropbox_test_folder):
        """FI3 at Level 3: Verify --backup-dir works with Dropbox."""

    def test_tpslimit_prevents_rate_errors(self, dropbox_test_folder):
        """FI5 at Level 3: Sync 50 files with tpslimit=8, verify no 429s."""


@pytest.mark.internet_required
class TestDropboxAuth:
    """Authentication handling with real Dropbox."""

    def test_valid_token_authenticates(self, dropbox_config):
        """Verify test account credentials work."""

    def test_expired_token_reports_helpful_error(self):
        """Verify auth errors suggest 'rclone config reconnect'."""


@pytest.mark.internet_required
class TestDropboxRateLimits:
    """Rate limit behavior with real Dropbox API."""

    def test_rate_limit_error_identified(self, dropbox_test_folder):
        """When rate limited, error.category == 'rate_limit'."""

    def test_rate_limit_retry_succeeds(self, dropbox_test_folder):
        """After rate limit, retry eventually succeeds."""
```

## Trade-offs Accepted

- **Slower CI**: Level 3 tests require internet and take longer. Accept this for real confidence.
- **Flakiness risk**: Network tests can fail transiently. Mitigate with `@pytest.mark.flaky(reruns=3)`.
- **Test account maintenance**: Token may expire, require manual refresh. Document the process.
- **Cost**: Dropbox API has rate limits. Design tests to stay within limits.

## Constraints

### For python-coder

1. **NO MOCKING** of subprocess, rclone, or Dropbox. Use dependency injection.
2. **Design for testability**: Pure functions for command building, parsing.
3. **Level 3 tests are MANDATORY** for feature-61 completion.
4. All tests must clean up after themselves (fixture-based cleanup).

### For python-reviewer

1. **REJECT** any PR that adds only Level 2 tests for Dropbox-specific behavior.
2. **VERIFY** Level 3 infrastructure exists before approving feature-61.
3. **VERIFY** error messages suggest actionable fixes.

## Abort Conditions

Downstream skills MUST ABORT if:

1. `DROPBOX_TEST_TOKEN` not available and Level 3 tests required
2. Dropbox test account becomes inaccessible
3. Rate limits prevent running tests (indicates design flaw in test isolation)

## Compliance

Feature-61 is NOT COMPLETE until:

- [ ] Level 1 tests exist for all pure functions
- [ ] Level 2 tests exist for local backend sync
- [ ] Level 3 tests exist for real Dropbox sync
- [ ] Level 3 infrastructure documented (test account setup)
- [ ] `DROPBOX_TEST_TOKEN` available in CI secrets
- [ ] All Level 3 tests pass with real Dropbox

---

*This ADR is BINDING. The coder implements exactly this strategy. The reviewer rejects deviations.*
