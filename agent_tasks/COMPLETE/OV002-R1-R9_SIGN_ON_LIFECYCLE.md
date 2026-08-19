id: OV002-R1-R9
status: COMPLETE
priority: 120
risk: HIGH
owner: Codex
base_branch: css-v1.0.1-maintenance
starting_head: a0bb7149534e03a72af64ead3ea0c623dd0fba8f
claimed_branch: css-v1.0.1-maintenance
claimed_starting_head: a0bb7149534e03a72af64ead3ea0c623dd0fba8f
claimed_at_utc: 2026-08-18T00:38:05Z
review_ready_at_utc: 2026-08-18T00:58:49Z
review_accepted_at_utc: 2026-08-18T01:58:00Z
closed_at_utc: 2026-08-18T01:58:00Z
lifecycle_reconciled_utc: 2026-08-19T18:59:40Z
commit_authority: NONE
push_authority: NONE
live_trading_authority: NONE

# OV002-R1-R9 - Sign-On Lifecycle / Runtime Establishment Remediation

## Objective

Determine and correct the canonical CSS sign-on lifecycle defect that caused
`[SESSION STOPPED] Sign-on cancelled by operator.` during the R10 startup,
followed by `process_identity_unavailable:CSS Runtime`.

Trace the canonical path from `launch_css.bat` through the launcher, CSS
Runtime service, dashboard startup, `authenticate_startup_user()`,
`await_login_ready_state()`, and `await_gui_login()`. Establish a
deterministic root cause before editing and make only the minimum safe
correction required for legitimate pending authentication and successful
runtime establishment.

## Safety boundary

Preserve authentication, password/session controls, RBAC, supervisor and
strong-process-identity controls, execution/risk gates, and fail-closed
behavior. Do not bypass or fabricate authentication, suppress genuine
identity failures, authenticate brokers, enable live execution, start the
OV002 endurance monitor, or start Attempt 3.

Add deterministic regression coverage for pending login, successful
authentication, explicit cancellation, malformed/failed authentication,
unchanged launcher identity behavior, and false runtime establishment after
authentication cancellation.

## Validation

Run the directly affected authentication/dashboard tests, launcher tests,
OV002 runtime-establishment/process-identity/supervisor/persistence/path
sentinels, compile changed Python files, and `git diff --check`. A controlled
non-OV002 startup smoke is permitted only after tests pass and must not start
the endurance monitor or create an Attempt-3 evidence package.

## Governance

Implementation remains uncommitted and unpublished. On completion, record
exact files, tests, limitations, and final Git state, then move this task to
`agent_tasks/REVIEW/` for independent review. Do not mark COMPLETE without
independent review.

## Implementation Evidence

### Files changed

- `dashboard/auth/css_sign_on.py`
- `tests/test_css_signon_lifecycle.py`
- this task record

### Root cause

The canonical launcher did not terminate or detach the dashboard child. The
Tk sign-on code mapped every post-`mainloop()` result without an authenticated
context to `CSS_SIGN_ON_CANCELLED`, including an unclassified UI teardown.
R10 therefore proved that the Tk lifecycle had ended without a context, but
its log could not distinguish explicit operator cancellation from unexpected
UI termination.

### Remediation

Explicit Exit, password-change Cancel, and window-close callbacks now record
an explicit cancellation reason. Authenticated contexts must be non-empty
dictionaries. A mainloop return without either condition raises the distinct
fail-closed `CSS_SIGN_ON_UI_TERMINATED` error; no authentication or identity
control is bypassed.

### Validation

- Focused lifecycle/auth suite: `25 passed`.
- `tests/test_css_runtime_launcher.py`: `69 passed`.
- `tests/test_auto_restart_framework.py tests/test_auth_observability.py`: `44 passed`.
- `tests/test_phase171b_supervisor_path_isolation.py tests/test_css_runtime_supervisor.py`: `32 passed`.
- `tests/test_ov002_r1_r1_blocker_repairs.py`: `223 passed`.
- `tests/test_ov002_r1_continuity_remediation.py tests/test_ov002_endurance_monitor.py`: `22 passed`.
- Python compilation and `git diff --check`: passed.

No CSS runtime, endurance monitor, Attempt 3, broker authentication, live
execution, commit, or push was performed. A real non-OV002 startup smoke was
not performed because it requires an interactive authenticated session.

## Independent Review / Closure

Independent review accepted the remediation. Controlled non-OV002 smoke
confirmed the responsive Tk sign-on remained alive while awaiting input;
explicit window closure shut down CSS Runtime fail-closed. No authenticated
context was fabricated and no broker or live-execution action occurred.

Final disposition: `OV002_R1_R9_REVIEW_ACCEPTED`.
