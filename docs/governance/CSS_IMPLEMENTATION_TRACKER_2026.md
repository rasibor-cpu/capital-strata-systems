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

Blocking items:
- full subsystem migration is intentionally deferred
- persistent event-bus storage is not yet implemented
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
