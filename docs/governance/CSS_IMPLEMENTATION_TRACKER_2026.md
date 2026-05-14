# Capital Strata Systems (CSS)
## Implementation Tracker 2026

Status: Active Institutional Implementation Tracker

---

## Purpose

This document tracks CSS implementation progress against the institutional governance framework.

The objective is to:

- connect governance doctrine to actual code implementation
- track outstanding institutional work
- prevent duplicated AI-agent work
- support Codex / Claude / Gemini continuation
- support PCNRASS verification
- support deployment readiness tracking

---

## Current Implementation Status

### Foundational Institutional Agenda

Status:
Materially Complete

Notes:
The original 25-point institutional stabilization agenda is materially complete based on prior validation reports.

---

### Phase 26–31 Institutional Hardening

Status:
Complete

Includes:
- IBKR-style instrument coverage registry
- end-to-end trade lifecycle audit
- live/paper mode reconciliation tests
- broker readiness certification
- global live-order kill switch
- role permission matrix tests

Validation:
Prior reports indicated 77 tests passed and smoke suites passed.

---

### Phase 34 Broker Balance Reconciliation

Status:
Complete

Known implementation:
- broker balance reconciliation engine
- broker reconciliation test coverage
- frontend/API contract exposure
- mobile reconciliation visibility

Remaining risk:
Snapshot-based reconciliation only. Live adapters must feed safe snapshots.

---

## Priority Implementation Backlog

### Priority 1 — Audit Trail Viewer Completion

Governance Dependencies:
- Audit Infrastructure Index
- Release Governance
- Observability Governance

Status:
Complete

Implemented:
- runtime audit viewer
- mobile audit viewer and export endpoint
- category/status/actor/source/time filtering
- export-safe redacted JSON payloads
- deterministic replay handoff
- no secret exposure in tested payloads

---

### Priority 2 — Trade Replay / Simulation Harness

Governance Dependencies:
- Replay Governance
- Audit Infrastructure Index
- Data & Payload Governance

Status:
Complete

Implemented:
- deterministic replay harness
- expected vs actual comparison
- lifecycle reconstruction
- governance and broker event reconstruction summaries
- replay-safe redacted serialization
- mobile audit replay endpoint
- unified replay correlation foundation
- normalized replay event envelopes
- lifecycle replay sink/viewer compatibility for legacy and envelope records
- read-only replay timeline grouping by correlation, symbol, cycle, and event sequence

---

### Priority 3 — Full WebSocket Frontend Migration

Governance Dependencies:
- WebSocket Governance
- Data & Payload Governance
- Mobile Governance
- Observability Governance

Status:
Foundation complete

Implemented:
- typed websocket delta events
- aggregate legacy delta compatibility
- web client typed-event consumption
- reconnect handling
- heartbeat payloads
- stale sequence detection helpers
- runtime-event-to-websocket compatibility adapter

Remaining:
- deeper mobile websocket live-view migration can be added as a future enhancement

---

### Priority 4 — Release Checklist Automation

Governance Dependencies:
- Release Governance
- Operational Risk Governance
- Observability Governance

Status:
Complete

Implemented:
- one-command PCNRASS validation script
- compile checks
- dashboard/engine tests
- runtime, web, auth, and mobile smoke tests
- JSON release summary output

Remaining:
- release-note publishing and remote tag push remain manual until explicitly requested

---

### Priority 5 — Production Deployment Profiles

Governance Dependencies:
- Deployment Governance
- Security & Access Governance
- Operational Risk Governance

Status:
Complete

Implemented:
- local deployment profile
- LAN/mobile deployment profile
- VPS/cloud test profile
- production deployment profile
- secure defaults and fail-closed validation helpers

---

### Priority 6 — Persistent Session Store

Governance Dependencies:
- Security & Access Governance
- Operational Risk Governance

Status:
Complete

Implemented:
- restart-safe hashed-token session persistence
- session expiration handling
- mobile session restoration support
- logout revocation

---

### Priority 7 — Database-Backed User Management

Governance Dependencies:
- Security & Access Governance

Status:
Complete

Implemented:
- optional SQLite-backed user store via CSS_AUTH_STORE=db
- existing hashed credential schema preserved
- RBAC payload persistence
- JSON user store remains default for backward compatibility

---

### Priority 8 — Alerting Layer

Governance Dependencies:
- Observability Governance
- Operational Risk Governance
- Mobile Governance

Status:
Complete

Implemented:
- broker disconnect alerts
- reconciliation drift alerts
- credential/security alerts
- drawdown/risk breach alerts
- session lock and defensive-mode alerts
- execution rejection alerts
- runtime API alert endpoint
- mobile API alert endpoint

---

## Post-Backlog Product Queue

### Market-Facing Companion App

Status:
Specification queued

Reference:
- docs/product/CSS_MARKET_COMPANION_APP_SPEC_2026.md

Working product names:
- CSS Pulse
- CSS Sentinel
- CSS Intelligence Hub

Scope:
- public/controlled-access marketing and intelligence companion app
- investor/client demo support
- safe replay/demo views
- lead capture and demo request workflows

Boundaries:
- no trade execution
- no broker credentials
- no live account data
- no alpha/proprietary decision-rule exposure
- no public control of CSS Core

Next steps:
- choose preferred product name
- approve wireframes
- approve safe sample datasets
- create a separate implementation directive only after approval

---

## Institutional Elevation Backlog

### Phase 41 - Broker Live Dry-Run Certification

Status:
Foundation complete

Implemented:
- broker live dry-run certification service
- API-safe certification payload
- fail-closed broker readiness checks
- credential-presence checks without secret exposure
- broker reconciliation dependency
- non-executing dry-run order probe validation
- JSONL certification log helper
- focused dashboard test coverage

Remaining:
- approved operator workflow must supply real broker-specific dry-run probe evidence
- unrestricted live trading remains blocked until live certification, operator approval,
  and PCNRASS release checks are complete

### Phase 42 - Broker Adapter Conformance Suite

Status:
Foundation complete

Purpose:
Validate all executable broker adapters against a common capability and snapshot
contract before they are eligible for live workflows.

Implemented:
- broker adapter conformance service
- API-safe conformance payload
- paper adapter coverage for OANDA, Alpaca, IBKR, and Binance
- capability registry additions for IBKR and Binance paper adapters
- denied-envelope refusal checks
- focused conformance tests

Remaining:
- live adapter conformance should be added only after explicit operator approval
  and live-safe adapter contracts are available

### Phase 43 - Live Credential Readiness Attestation

Status:
Foundation complete

Implemented:
- redacted live credential attestation service
- API-safe attestation payload
- Coinbase, OANDA, and Alpaca requirement checks
- local env/key-path presence checks only
- no network calls
- no credential values or local paths exposed
- focused credential attestation tests

Remaining:
- credential expiry and rotation checks require broker/key-provider metadata
  that is not present in the current local credential format
- real live approval still requires operator review and broker-specific dry-run
  certification evidence

### Phase 9B - Live-Readiness Certification Framework

Status:
Foundation complete

Implemented:
- broker-layer live-readiness certifier
- PASS/FAIL certification result object
- explicit broker identity validation
- adapter availability validation
- broker asset-class support validation
- credential file presence and safe-load validation
- capital-source and balance-source separation checks
- dry-run-only order safety checks
- CSSUnifiedTradeGate approval path check
- valid-session and known-engine-mode checks
- explicit operator approval requirement
- redacted audit payload and JSONL log helper
- deployment documentation
- focused engine tests

Live-trading status:
Still not approved. A PASS result means readiness evidence is complete for review;
it does not enable live execution or bypass operator approval.

Remaining:
- real broker-specific dry-run evidence
- operator-approved live runbook
- kill-switch verification
- clean broker reconciliation immediately before any restricted live session

---

## Readiness Tracking

### Replay Readiness

Status:
Complete

Blocking items:
- none for current scope

---

### WebSocket Readiness

Status:
Foundation complete

Blocking items:
- deeper mobile websocket live-view migration remains optional future enhancement

---

### Runtime Event Bus Readiness

Status:
Foundation complete

Implemented:
- canonical runtime event object
- in-process publish/subscribe bus
- recent event retrieval and testing clear helper
- JSON-safe redaction for event payloads
- replay-envelope compatibility adapter
- websocket compatibility adapter
- alert payload adapter
- optional trade lifecycle service publisher hook
- shadow-mode websocket delta publishing hook
- shadow-mode alert-created publishing hook
- shadow-mode replay-persisted publishing hook
- non-fatal event bus publishing by default, with strict mode for tests
- read-only runtime event inspection helper
- `/api/v1/runtime-events` inspection endpoint
- `/runtime-events` operator inspection page
- filterable recent-event view by event type, subsystem, severity, correlation id, and limit
- runtime event retention/export policy object
- JSON-only read-only export helper
- inspection and export limit caps
- export redaction enforcement without automatic persistence
- guarded runtime event persistence approval policy
- validation-only persistence request evaluator
- read-only `/api/v1/runtime-event-persistence-policy` policy endpoint
- audit-safe approval result payload with token redaction
- runtime event persistence architecture design document
- dry-run runtime event persistence simulator
- read-only `/api/v1/runtime-event-persistence-sim` simulation endpoint
- simulator enforcement of retention, approval, subsystem, and redaction policy
- operator runtime event persistence simulator review page
- simulator summary, rejection, subsystem, warning, and empty-state rendering
- simulator-only runtime event storage backend profiles
- read-only `/api/v1/runtime-event-persistence-scenarios` scenario endpoint
- backend comparison, recommendation, governance blocker, and storage estimate reporting
- audit-safe runtime event persistence dry-run report builder
- read-only `/api/v1/runtime-event-persistence-report` JSON report endpoint
- operator dry-run report, safety assertion, and approval requirement rendering
- operator runtime event persistence approval checklist builder
- read-only `/api/v1/runtime-event-persistence-checklist` checklist endpoint
- checklist readiness, failed-check, warning, and operator-review rendering
- read-only checklist export package builder
- read-only `/api/v1/runtime-event-persistence-checklist-export` JSON export endpoint
- print-friendly `/runtime-event-persistence-checklist-print` operator review page
- export/print safety disclaimer confirming persistence remains disabled
- browser-validated desktop, tablet, mobile, and print checklist export artifacts
- phone-width print surface containment and checklist control wrapping

Blocking items:
- full subsystem migration is intentionally deferred
- persistent event-bus storage is not yet implemented
- event-bus persistence remains disabled by default and is not activated by validation
- storage backend selection is modeled but not yet approved
- cross-process queueing is not yet implemented

---

### Deployment Readiness

Status:
Restricted deployment profile ready; unrestricted live deployment still requires operator approval

Blocking items:
- live broker credential validation
- live broker-specific dry-run certification
- operator approval for production/live mode

---

### Live Trading Readiness

Status:
Not approved

Implemented:
- controlled micro-live pilot readiness model
- read-only `/api/v1/micro-live-pilot-readiness` endpoint
- operator `/micro-live-pilot-readiness` review dashboard
- non-executing micro-live pilot order-intent evidence package
- read-only `/api/v1/micro-live-pilot-order-intent` endpoint
- operator review display of order-intent blockers and required approvals
- Coinbase non-executing micro-live dry-run probe evidence package
- read-only `/api/v1/coinbase-micro-live-dry-run-probe` endpoint
- operator display of dry-run probe status, blockers, warnings, and no-submit
  state
- operator approval and kill-switch verification evidence gate
- read-only `/api/v1/micro-live-operator-approval-gate` endpoint
- operator display of approval status, trading-armed false state, kill-switch
  evidence, and remaining manual approval blockers
- final micro-live broker readiness confirmation evidence package
- read-only `/api/v1/micro-live-broker-readiness-confirmation` endpoint
- operator display of Coinbase/BTC-USD/limit-only readiness, broker-mutation
  false state, order-submit false state, credential exposure status, and
  remaining broker confirmation blockers
- explicit pilot constraints: Coinbase Advanced, BTC-USD, CAD $15 maximum,
  one limit order, 0.35% maximum slippage, mandatory logging, mandatory
  post-trade pause, and fail-closed governance
- unrestricted live trading and automatic live execution remain disabled

Blocking items:
- restricted live governance review
- broker reconciliation confidence
- kill-switch verification
- release automation
- audit/replay verification
- production observability

---

## PCNRASS Requirements

Every implementation phase must include:

- rollback tag
- compile validation
- smoke validation
- relevant unit tests
- regression review
- documentation update
- PCNRASS confirmation

---

## AI Agent Execution Guidance

### Codex

Preferred use:
- structured implementation
- compile/test loops
- repo-aware changes
- PCNRASS phase execution

---

### Claude

Preferred use:
- architecture-sensitive continuation
- audit review
- replay/audit/system reasoning
- phase-scoped implementation review

---

### Gemini / Anti-Gravity

Preferred use:
- secondary validation
- comparative audit
- UI scaffolding
- implementation review

---

## Current Recommended Next Action

Recommended next engineering priority:

1. Run PCNRASS release checklist before every commit or push
2. Keep live trading restricted until real broker-specific dry-run probe evidence is supplied and approved
3. Implement Phase 44 operator approval workflow as the next bounded elevation item
4. Continue dashboard separation only in bounded, no-regression slices
5. Treat new feature ideas as post-backlog enhancements

No unrestricted live trading should occur without operator approval, broker certification, and PCNRASS-confirmed release checks.
