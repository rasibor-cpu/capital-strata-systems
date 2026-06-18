# ARP-002B Live Toggle RBAC Remediation Report

## Original Audit Finding

ARP-001 verified audit finding B-02: `backend/app/security/live_toggle.py` authorized LIVE execution using a hardcoded identity check:

```text
ctx.user_id == "1369"
```

This created a user-specific authorization bypass risk and did not align with CSS role/permission governance.

## Verification Result

Status: REMEDIATED

Verification confirmed that `live_toggle.py` used a hardcoded user ID for LIVE mode authorization. The module also referenced a stale audit-context function name. The current audit-context authority exposes `require_audit_user()` and `AuditUser` with `user_id`, `role`, `unit_code`, and `branch`.

Existing CSS permission concepts reviewed include:

* `SUPER_USER` role authorization
* dashboard role-profile permissions such as `can_execute_live_trading`
* existing RBAC/access-control modules under `backend/security` and `engine/security`
* audit user binding under `backend/app/observability/audit_context.py`

## Files Reviewed

* `backend/app/security/live_toggle.py`
* `backend/app/observability/audit_context.py`
* `backend/app/security/access_control.py`
* `backend/security/permissions.py`
* `engine/security/rbac.py`
* `engine/security/access_control.py`
* `engine/run_engine.py`
* `tests/test_security_phase_alpha.py`

## Files Changed

* `backend/app/security/live_toggle.py`
* `tests/test_live_toggle_rbac.py`
* `docs/governance/ARP_002B_LIVE_TOGGLE_RBAC_REMEDIATION_REPORT.md`
* `certification/security/SECURITY_CERTIFICATION_EVIDENCE_REGISTER.md`

## Previous Hardcoded Behavior

Previous LIVE mode authorization allowed the live toggle only when the audit context user ID matched `1369`, regardless of broader role or permission governance. This meant authorization was bound to one identity instead of a CSS role/permission control.

## New RBAC Behavior

LIVE mode authorization is now based on role/permission checks:

* `SUPER_USER` role is authorized.
* Explicit `can_execute_live_trading=True` permission is authorized when supplied in a user context or role profile.
* A non-`SUPER_USER` role without explicit live-execution permission is blocked.
* The hardcoded `1369` user ID is no longer required and no longer grants authorization by itself.

The public execution-boundary function remains:

```text
require_live_allowed(...)
```

It still only authorizes the live-toggle boundary. It does not place orders, call broker APIs, set broker live-execution environment flags, or bypass broker firewalls.

## Fail-Closed Rules

The live toggle blocks LIVE mode if:

* user context is missing
* role is missing
* role is not authorized
* explicit live-execution permission is absent or false
* audit user context cannot be resolved
* engine mode is not `LIVE`

TEST mode remains blocked at this boundary with `EXECUTION_BLOCKED_TEST_MODE`.

## Tests Added Or Updated

Added:

* `tests/test_live_toggle_rbac.py`

Coverage includes:

* hardcoded user ID is no longer required
* unauthorized user is blocked
* missing context fails closed
* `SUPER_USER` role is allowed
* explicit `can_execute_live_trading` permission is allowed
* non-`SUPER_USER` without permission is blocked
* missing role fails closed
* live toggle does not enable broker execution flags

## Validation Results

Validation commands for this phase:

```text
.venv\Scripts\python.exe -m py_compile backend/app/security/live_toggle.py
.venv\Scripts\python.exe -m pytest tests/test_live_toggle_rbac.py tests/test_security_phase_alpha.py -q
```

Results are recorded in the final Codex delivery for this phase.

## Boundary Confirmation

This phase did not:

* modify AntiBleedGuard
* modify MarginTradeGate
* modify live_arm
* modify broker adapters
* modify dashboard behavior
* modify credential handling
* place trades
* call broker APIs
* enable live broker execution
* change strategy logic

## Remaining Risks

* `engine/run_engine.py` still references an older audit-context shape for startup logging. This phase did not remediate that broader runtime compatibility issue because the scope was limited to `live_toggle.py`.
* Final production certification still requires retained RBAC role-matrix evidence, live execution denial logs, and Robert review.

## Certification Evidence Impact

This report provides captured remediation evidence for B-02. The security certification evidence register references this report as captured evidence for RBAC live-toggle authorization. It is not marked approved; Robert review remains required before merge or further remediation.
