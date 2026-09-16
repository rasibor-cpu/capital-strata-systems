# CSS UAT Cycle 1 Acceptance Report — 2026-09-16

Status: ACCEPTED FOR CONTROLLED FULL-SYSTEM TESTING

Candidate SHA before this documentation-only report:
602a733742f948575cc7712894984a599ec625bf

Baseline:
0c9889381f70d35c3aed226a1dbc2c59213d0015

## Scope

Cycle 1 expanded acceptance beyond commercialization economics to include:

- exact contract-version enforcement;
- restart persistence;
- sandbox payment idempotency;
- sandbox notification idempotency;
- sandbox/production provider separation;
- Launch Ops read-only controls;
- customer/operator web route and disclosure smoke coverage; and
- broker live-execution fail-closed controls.

The mandatory commercialization UAT catalog now contains 19 scenarios.

## Defect discovered during UAT

### UAT-DEFECT-001 — Web application runtime API routes absent

Severity: HIGH for acceptance / integration
Status: CLOSED

Observed:
The customer/operator page shell loaded, but the web application's runtime API
and websocket routes were absent from FastAPI's materialized route table under
the current FastAPI/Starlette version.

Impact:
A deployed web shell could render while required runtime API endpoints were not
available, causing customer/operator controls and dashboards to fail at runtime.

Root cause:
dashboard/web/web_app.py still used FastAPI include_router while the runtime API
bridge had already adopted direct route materialization to handle framework
version drift.

Remediation:
The web app now constructs the governed routers and extends app.router.routes
with their existing route objects, matching the proven runtime API
compatibility pattern.

Validation:
The customer/operator web smoke subsequently passed.

## Final automated evidence

All required acceptance gates passed on candidate
602a733742f948575cc7712894984a599ec625bf.

- CSS Governance Validation: PASS
- CSS Full Regression Remote: 1,977 / 1,977 PASS
- Expanded CSS Commercialization UAT: 292 / 292 PASS
- Customer and Operator Web Smoke: PASS
- CSS Full Test Release Candidate: PASS

Integrated full-test readiness reported:

- ready_for_full_testing = true
- uat_complete = true
- launch_dossier_complete = true
- sandbox_payment_succeeded = true
- sandbox_notification_succeeded = true
- production_commercial_ready = false
- trading_execution_authority = false
- broker_execution_authority = false
- money_movement_to_external_provider = false
- production block:
  PAYMENT_PREFLIGHT:PAYMENT_PROVIDER_NOT_PRODUCTION_ENVIRONMENT

## Acceptance decision

UAT Cycle 1 is ACCEPTED for the controlled full-test environment.

The acceptance means the implemented customer, operator, accounting,
commercialization, persistence, sandbox-provider, web integration, and
execution-safety flows meet the current automated acceptance criteria.

It does not authorize live trading, real customer charging, real notification
delivery, or production launch.

## Remaining production-only evidence

Production remains fail-closed pending genuine external evidence for legal and
regulatory approval, real payment/notification providers, real-environment
security/restore/rollback testing, production-like provider UAT,
reconciliation certification, and authorized release-owner sign-off.

## Repository note

The pre-existing CSS-CLAUDE gitlink cleanup warning remains documented and
non-blocking. Existing governance explicitly excludes it from normal
modification.
