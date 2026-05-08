# CSS Phase 26-40 Institutional Hardening Plan

Date: 2026-05-08

This plan extends the completed 25-point agenda. It is intentionally
governance-first and keeps `DashboardState` as the canonical frontend bridge.

## Status

- Phase 26: IBKR-style instrument coverage registry and broker capability payload - complete
- Phase 27: End-to-end trade lifecycle audit - complete
- Phase 28: Live/paper mode reconciliation tests - pending
- Phase 29: Broker readiness certification layer - pending
- Phase 30: Live order kill switch - pending
- Phase 31: Role-based permission matrix tests - pending
- Phase 32: Audit trail viewer - pending
- Phase 33: Trade replay and simulation harness - pending
- Phase 34: Broker balance reconciliation - pending
- Phase 35: Production deployment profiles - pending
- Phase 36: Persistent session store - pending
- Phase 37: Database-backed user management - pending
- Phase 38: Alerting layer - pending
- Phase 39: Full websocket frontend migration - pending
- Phase 40: Institutional system health and release checklist automation - pending

## Phase 26 Scope

The first hardening step is to stop treating "multi-asset" as an informal
claim. CSS now needs a canonical product coverage registry that distinguishes:

- IBKR-style product family coverage
- CSS workflow visibility
- paper execution support
- live execution certification

This phase does not add broker execution for new product families. It only
registers coverage and exposes frontend-safe broker capability metadata so the
web/mobile surfaces can report readiness without direct broker access or
credential leakage.

## PCNRASS Boundaries

- No direct broker calls from frontend code.
- No credentials in payloads or logs.
- No live execution expansion without a separate broker-certified phase.
- DashboardState remains the canonical frontend bridge.
- Paper-first safety remains mandatory.
