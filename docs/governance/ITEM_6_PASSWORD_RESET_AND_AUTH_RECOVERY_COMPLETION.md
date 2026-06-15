# Item 6 Password Reset and Authentication Recovery Completion

## Scope

Item 6 completes the active CSS local authentication recovery capability while preserving existing authentication, RBAC, session management, legal acceptance, and security controls.

This phase does not change broker permissions, live-trading controls, dashboard behavior, risk behavior, margin behavior, execution behavior, credential handling, or trading logic.

## Current State Reviewed

### Current Login Flow

CSS currently has two authentication surfaces:

1. `backend/app/auth/auth_router.py`
   - FastAPI username/password login.
   - OTP generation and verification.
   - Bearer session token creation through `token_store`.
   - Superuser password remains environment-driven through `REA_SUPERUSER_PASSWORD`.

2. `backend/app/security/auth_gate.py`
   - Local operator login gate used by runtime/security flows.
   - Imports `backend.app.security.user_registry` fail-closed.
   - Prompts for user ID and password.
   - Enforces first-login password change through the registry compatibility layer.

### Current Session Restoration Flow

Session token validation for the API auth surface remains owned by:

```text
backend/app/auth/token_store.py
```

Runtime session persistence remains owned by:

```text
backend/app/persistence/repositories/session_repository.py
backend/app/persistence/services/session_runtime_service.py
```

This phase did not change session restoration or session persistence behavior.

### Current User Persistence

The active local user registry persists users in:

```text
data/users.json
```

through:

```text
backend/app/security/user_registry.py
```

Passwords are stored as hashes, not plaintext.

### Existing Password Change Capability

Before this phase, `user_registry.change_password(...)` could update a password after user identification, but:

- it did not return a boolean success value expected by the auth gate compatibility wrapper
- it did not provide an administrator-initiated recovery reset path
- the registry did not expose public read helpers used by the auth gate compatibility path

### Missing Recovery Functionality

The missing capability was a safe, auditable local account-recovery primitive:

```text
administrator/SUPER_USER initiated password reset
```

No default password, hidden account, backdoor account, broker permission change, or live-trading permission change was acceptable.

## Implementation

### User Registry Completion

Updated:

```text
backend/app/security/user_registry.py
```

Added public helpers:

```text
load_users()
get_user(user_id)
```

Completed password change compatibility:

```text
change_password(user_id, new_password) -> bool
```

Added safe recovery reset:

```text
reset_password(
    user_id,
    temporary_password,
    *,
    authorized_by_role,
    require_change=True,
) -> bool
```

Reset authorization is limited to:

```text
ADMIN
SUPERUSER
SUPER_USER
```

Unauthorized reset attempts fail closed with:

```text
PASSWORD_RESET_FORBIDDEN
```

Unknown users and password policy failures continue to fail closed.

Reset attempts emit non-secret audit-friendly log messages:

```text
PASSWORD_RESET_BLOCKED
PASSWORD_RESET_COMPLETED
```

These messages include user ID, role, reason, and require-change state where applicable. Passwords and password hashes are not logged.

### Auth Gate Compatibility

Updated:

```text
backend/app/security/auth_gate.py
```

The compatibility password verification helper now treats the registry's successful `UserRecord` response from `authenticate(...)` as a valid authentication result while preserving fail-closed behavior for exceptions and invalid credentials.

## Security Controls Preserved

| Control | Status |
| ------- | ------ |
| Password hashing | Preserved |
| Plaintext password storage prohibited | Preserved |
| RBAC reset authorization | Added for reset path |
| Legal acceptance enforcement | Preserved |
| Session validation | Preserved |
| Hidden recovery accounts | Not added |
| Default passwords | Not added |
| Broker permissions | Not changed |
| Live-trading controls | Not changed |
| Credential handling | Not changed |

## Tests Added

Created:

```text
tests/test_password_reset_recovery.py
```

Coverage:

- administrator password reset succeeds
- old password is invalidated
- new temporary password works
- new password is hashed, not stored as plaintext
- unauthorized reset role fails closed
- unknown user reset fails
- password policy failure fails
- auth gate compatibility path verifies and changes passwords correctly
- legal acceptance remains fail-closed after password reset
- reset completion emits a non-secret audit-friendly log record

## Tests Executed

Compile validation:

```text
.\.venv\Scripts\python.exe -m py_compile backend\app\security\user_registry.py backend\app\security\auth_gate.py tests\test_password_reset_recovery.py
```

Result:

```text
PASS
```

Password reset tests:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_password_reset_recovery.py -q
```

Result:

```text
5 passed
```

Security and legal acceptance regression:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_security_phase_alpha.py tests\governance\test_phase1_legal_acceptance_implementation.py -q
```

Result:

```text
16 passed
```

## Certification Findings

Authentication recovery is now complete for the active local user registry path.

The reset workflow is administrator/SUPER_USER initiated, fail-closed, hash-preserving, and does not alter RBAC, legal acceptance, session validation, broker permissions, live-trading permissions, or trading behavior.

Certification status:

```text
PASS
```

## Remaining Notes

The FastAPI superuser auth surface remains environment-password based and intentionally does not provide runtime reset for `REA_SUPERUSER_PASSWORD`; that secret must continue to be managed through environment/operations procedures.
