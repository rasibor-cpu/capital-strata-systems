# CSS Phase 135E - Runtime Session Continuity

## Purpose

Phase 135E reports long-duration session continuity state for 24-72 hour paper validation. It explains session expiry and quiet mode without bypassing existing security.

## Session States

- `ACTIVE`: session is within max age.
- `EXPIRING_SOON`: session is near max age and operator reauthentication should be planned.
- `EXPIRED`: session has exceeded max age.
- `REAUTH_REQUIRED`: quiet mode or expiry requires operator reauthentication.
- `RESUMED`: existing authentication flow has restored session continuity.
- `UNKNOWN`: session evidence is unavailable.

## Quiet Mode

Quiet mode is preserved as a security behavior. When quiet mode is active, the monitor reports that reauthentication is required and paper execution should not continue until the existing authentication flow permits it.

## Reauthentication

The dashboard and API recommend reauthentication through the existing login flow. The monitor does not store credentials, perform automatic login, renew sessions, or bypass RBAC.

## Safety

Live execution remains false. This phase does not change broker execution, Runtime Supervisor decisions, Unified Trade Gate decisions, Capital Governor behavior, RBAC, AntiBleedGuard, or Portfolio Risk Committee governance.

## Validation

Run:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_runtime_session_continuity.py tests/test_phase135e_runtime_health.py tests/test_phase135e_validation_readiness.py tests/test_phase135e_dashboard.py -q
```
