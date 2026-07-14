# Governance Document - Secure Sign-On Session Persistence Restoration
## Phase 163B.3L

---

### 1. Objective
Complete the sign-on persistence framework to enable secure, automatic session restoration from `css_auth_session.json` across process restarts on `Laptop1`, eliminating the need for manual console logins when a valid, unexpired session is available.

### 2. Previous Write-Only Gap
Previously, the login session was persisted via `persist_login_session()` into `css_auth_session.json` upon successful authentication, but it was never read back or checked during startup. The persistence logic acted only as a one-way saved log file, forcing operators to execute a complete console login session on every startup.

### 3. Trust Boundaries
* **Registry Dominance:** The persisted session file (`css_auth_session.json`) is treated as untrusted and is fully validated. Role definitions and permission configurations are derived directly from the canonical user registry (`data/users.json`).
* **Encryption Boundaries:** Plaintext passwords, session secrets, private keys, and broker tokens are strictly excluded from the persisted JSON record.
* **Storage Isolation:** The session file is saved locally under the `artifacts/` folder, which is git-ignored and isolated from repository pushes.

### 4. Persisted-Data Schema
The persisted JSON record maintains the original generated schema structure:
* `user_id`: Numeric string of the authenticated user.
* `display_name`: Display name of the user.
* `role`: User role matched against user registry (e.g. `SUPER_USER`, `VIEWER`).
* `unit_code`: Active business unit (e.g. `CORE`).
* `home_branch`: Active office code (e.g. `HQ`).
* `last_login`: ISO-86400 string containing timezone-aware UTC datetime.
* `login_persistence`: Boolean flag asserting persistence intent.

### 5. Canonical Registry Revalidation
Upon startup, the restoration logic reads `css_auth_session.json` and performs the following registry steps:
1. Loads the latest registry state via `load_users()`.
2. Validates that the persisted `user_id` exists in the registry.
3. Verifies that the persisted user record has matching `role` values.
4. Confirms that the user is not locked out (verifying the `"locked"` database flag and evaluating the `active_lockout_remaining_seconds` time-offset).

### 6. Expiry Behavior
* **Max Session Age:** Validates that the timestamp `last_login` is less than 24 hours (`86400` seconds) old compared to `datetime.now(timezone.utc)`. Naive timestamps are resolved as UTC.
* **Clock Skew and Future dated checks:** Rejects any session whose creation timestamp is more than 60 seconds in the future.
* **Fail-Closed Cleanup:** On expiration or timestamp invalidity, the file is immediately deleted via `invalidate_login_session()`.

### 7. Fail-Closed Cases
Restoration yields `None` (requiring full interactive sign-on) and immediately deletes the session file if:
1. The session file does not exist, is empty, or is corrupted.
2. The payload is not a valid JSON dictionary or lacks required keys.
3. The user ID is missing, blank, or not found in the registry.
4. The user is currently locked out or disabled.
5. The role does not match the registry configuration.
6. The session timestamp is malformed, in the future (> 60s), or expired (> 24 hours).

### 8. Startup Integration
* **Integration Point:** `restore_login_session(users)` is invoked at the entry of `await_login_ready_state()` directly after loading the user registry.
* **Clean Fallback:** If a session is missing or fails verification checks, the file is invalidated, and execution falls through to standard console/TUI sign-on logic without crashing.

### 9. Logout Invalidation
* **Invalidation Path:** Added `invalidate_login_session()` which unlinks the session file safely.
* **Integration:** Integrated `invalidate_login_session()` into the `close_active_session` function of `scripts/css_live_dashboard.py` to ensure that standard operator session close/logout safely clears the persisted file.

### 10. Security Exclusions
* Plaintext passwords, hashed credentials, private keys, API configurations, or encrypted payloads are never persisted or read by the session controller.

### 11. Tests Performed
A complete test suite was implemented in [`tests/test_signon_persistence_restoration.py`](file:///C:/rasib/source/capital-strata-systems/tests/test_signon_persistence_restoration.py) verifying 20 separate scenarios:
* Missing session file fallback.
* Successful validation and user context restoration.
* Rejection of corrupted, empty, or non-object payloads.
* Rejection of missing keys or wrong data types.
* Rejection of unknown, locked-out, or modified users.
* Rejection of future-dated, expired, or malformed session timestamps.
* Exclusivity of user context details (no secret credentials loaded).
* Clean fall-through to console login when session is invalid.
* Invalidation on logout.

All 20 tests pass cleanly with zero warnings:
```text
20 passed in 1.13s
```

### 12. Rollback Boundary
To roll back this phase, discard changes to `dashboard/auth/css_sign_on.py` and `scripts/css_live_dashboard.py`, and delete the test file `tests/test_signon_persistence_restoration.py` and this document.

### 13. Confirmation of System Preservation
* **Execution & Broker Safety:** I confirm that all live execution blocks, advisory-only boundaries, margin gates, pilot limits, and PCNRASS safety protocols are unchanged. No broker communication logic or live trading components were modified.
