# CSS Full-Test Release Candidate Runbook

Status: INTERNAL ENGINEERING COMPLETE TARGET — PRODUCTION APPROVALS STILL EXTERNAL

## Purpose

This runbook produces a deterministic CSS release candidate that is ready for
full testing without activating real customer charging, real notification
delivery, broker execution, or external money movement.

## One-command full-test readiness

Run from the repository root:

    CSS_FULL_TEST_MODE=1 python scripts/run_css_full_test_readiness.py

The script:

1. refuses to use the normal CSS runtime database;
2. deletes/recreates only the dedicated disposable full-test database;
3. applies all current migrations;
4. seeds synthetic evidence marked TEST_ONLY;
5. creates an expired synthetic trial and accepted agreement;
6. seeds synthetic legal, charging, security, jurisdiction-mode and provider
   approvals into the isolated test database;
7. marks every required commercialization UAT scenario passed;
8. creates a synthetic complete launch dossier;
9. runs an idempotent sandbox payment simulation;
10. runs an idempotent sandbox notification simulation;
11. evaluates the normal commercialization release status;
12. proves production release remains blocked because the payment provider is
    sandbox-only; and
13. proves broker/trading authority and external money movement remain false.

Exit code 0 means the integrated sandbox release candidate is ready for full
testing. Any violated invariant returns a non-zero exit code.

## CI gates

The release-candidate PR must pass all of the following independently:

- CSS Governance Validation;
- CSS Full Regression Remote;
- CSS Commercialization UAT; and
- CSS Full Test Release Candidate.

The full-test RC workflow itself also compiles the major Python trees, runs the
entire pytest suite, and then executes the integrated sandbox readiness runner.

## Safety separation

Synthetic approvals are guarded by CSS_FULL_TEST_MODE=1 and are written only to
the dedicated disposable full-test database. Their evidence references begin
with TEST_ONLY.

The sandbox payment provider has no network integration. The sandbox
notification provider has no external delivery integration.

A sandbox payment provider is explicitly prohibited from satisfying production
payment preflight. Therefore the full-test environment can be completely green
for testing while production-commercial readiness remains red.

## Production activation

Successful full testing does not replace real external evidence. Production
still requires the approved agreement, jurisdiction/regulatory determinations,
real security/restore/rollback evidence, live provider agreements/credentials,
real notification policies/provider configuration, production-like UAT,
reconciliation certification, and authorized release-owner sign-off.
