# CSS Institutional Elevation Backlog 2026

Status: Active post-foundation hardening queue
Governance protocol: PCNRASS

## Purpose

This backlog captures the next material work needed to move Capital Strata
Systems from a hardened internal trading platform toward a more institutional
operating standard. These items are intentionally additive and bounded. They do
not authorize unrestricted live trading, broad rewrites, or direct frontend
broker access.

## Phase 41 - Broker Live Dry-Run Certification

Status:
Foundation complete

Objective:
Create broker-specific certification that proves live-mode readiness from
sanitized snapshots and explicit dry-run probe results before any unrestricted
live operation is considered.

Required outcomes:
- fail-closed certification status
- broker readiness checks
- credential-presence checks without secret exposure
- reconciliation dependency
- non-executing dry-run order probe validation
- API-safe payload

Implemented:
- `dashboard/runtime/broker_live_dry_run_certification.py`
- `backend/app/brokers/live_readiness_certifier.py`
- `/api/v1/broker-live-dry-run-certification`
- focused certification tests
- broker-layer PASS/FAIL result object
- explicit operator approval requirement
- redacted audit payload/log helper

Remaining:
- real broker-specific dry-run probe evidence must be supplied by an approved
  operator workflow before live trading can be approved.

## Phase 42 - Broker Adapter Conformance Suite

Status:
Foundation complete

Objective:
Validate that Coinbase, OANDA, IBKR, and any future broker adapter expose the
same institutional capability contract before being used in live workflows.

Required outcomes:
- mode support checks
- asset-class capability checks
- account snapshot contract checks
- position snapshot contract checks
- order-intent validation contract checks
- fail-closed unsupported capability behavior

Implemented:
- `dashboard/runtime/broker_adapter_conformance.py`
- `/api/v1/broker-adapter-conformance`
- canonical paper adapter conformance report
- capability registry coverage for OANDA, Alpaca, IBKR, and Binance paper adapters
- denied-envelope refusal checks
- focused conformance tests

Remaining:
- live adapters must be added to the conformance suite only after explicit
  operator approval and safe adapter contracts are available.

## Phase 43 - Live Credential Readiness Attestation

Status:
Foundation complete

Objective:
Create redacted credential-readiness attestations that prove required secrets
are present and loadable without exposing the secrets themselves.

Required outcomes:
- no secret values in payloads or logs
- broker-specific required-field checks
- key-file and PEM path existence checks
- expiry/rotation warnings where possible
- local-only attestation output

Implemented:
- `dashboard/runtime/live_credential_attestation.py`
- `/api/v1/live-credential-attestation`
- Coinbase/OANDA/Alpaca requirement checks
- env key and local private-key path presence attestation
- no secret values or local paths in payloads
- focused credential attestation tests

Remaining:
- expiry and rotation checks require broker/key-provider metadata that is not
  available in the current local credential format.

## Phase 44 - Operator Approval Workflow

Objective:
Require explicit operator approval before restricted live mode can be armed.

Required outcomes:
- approval record
- approver role validation
- timestamped authorization
- expiration
- audit trail integration
- fail-closed missing approval behavior

## Phase 45 - Live Mode Runbook And Guardrail Gate

Objective:
Convert live-mode readiness into a repeatable runbook gate.

Required outcomes:
- pre-live checklist
- required evidence links
- kill-switch confirmation
- reconciliation confirmation
- dry-run certification confirmation
- release-check confirmation

## Phase 46 - Broker Balance Confidence Scoring

Objective:
Add confidence scoring around reconciliation quality before live mode.

Required outcomes:
- freshness score
- account match score
- position match score
- broker heartbeat score
- safe degradation threshold

## Phase 47 - Order Intent Simulator

Objective:
Simulate live order intents end-to-end without broker submission.

Required outcomes:
- normalized order-intent schema
- broker capability validation
- governance decision replay
- estimated cost summary
- no execution route

## Phase 48 - Incident Drill Harness

Objective:
Run deterministic incident drills for broker disconnects, divergence, risk
breaches, kill-switch activation, and session lock events.

Required outcomes:
- drill scenarios
- expected alert output
- expected safe-degradation behavior
- audit/replay output

## Phase 49 - Observability Retention And Export Policy

Objective:
Define and implement retention/export policy for audit, replay, alert, and
release summaries.

Required outcomes:
- retention configuration
- export-safe redaction
- local archive workflow
- size and rotation guardrails

## Phase 50 - Performance And Load Budget

Objective:
Define runtime and frontend performance budgets for dashboard snapshots,
websocket deltas, replay loading, and mobile views.

Required outcomes:
- budget thresholds
- smoke/performance tests
- payload size checks
- stale-state warnings

## Phase 51 - Configuration Change Governance

Objective:
Audit and gate changes to thresholds, modes, risk limits, and broker settings.

Required outcomes:
- config snapshot
- change diff
- approver metadata
- rollback reference
- audit event

## Phase 52 - Disaster Recovery Drill

Objective:
Prove restart, session restoration, replay continuity, and safe degradation
after a controlled restart or corrupted local artifact.

Required outcomes:
- recovery scenario definitions
- restart-safe session checks
- artifact corruption handling
- PCNRASS recovery report

## Phase 53 - Mobile Critical Flow Certification

Objective:
Certify mobile access for the critical operator flows that CSS supports.

Required outcomes:
- sign-on
- mode visibility
- broker status visibility
- kill-switch visibility
- read-only audit/replay views
- no frontend broker calls

## Phase 54 - Release Artifact Integrity

Objective:
Strengthen release automation with artifact hashes and immutable local release
summaries.

Required outcomes:
- release summary hash
- changed-file manifest
- validation command manifest
- PCNRASS evidence package

## Phase 55 - Companion App Wireframe Planning

Objective:
Move the queued CSS market-facing companion app from specification to approved
wireframes only after product name, audience, and safe sample-data boundaries
are approved.

Required outcomes:
- no CSS Core runtime changes
- wireframe-only output
- demo-data boundary approval
- separate implementation directive

## Execution Order

Recommended order:

1. Phase 41
2. Phase 42
3. Phase 43
4. Phase 44
5. Phase 45
6. Phase 47
7. Phase 46
8. Phase 48
9. Phase 50
10. Phase 54
11. Remaining phases by operator priority

## PCNRASS Rules

Every phase must:

- be bounded and additive
- avoid broker execution unless explicitly approved
- avoid credential exposure
- preserve DashboardState as the frontend bridge
- compile cleanly
- pass focused tests
- pass release checks before commit or push
- update this backlog or the implementation tracker
