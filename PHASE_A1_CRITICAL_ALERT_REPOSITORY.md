# PHASE A1: Canonical Critical Alert Repository

## Summary
This phase introduces a canonical backend alert repository for runtime and trading events with fail-closed persistence, deduplication, critical-event filtering, acknowledgment handling, and compatibility output for mobile/runtime alert consumers.

## Scope
- Added a canonical repository implementation in backend/monitoring/alert_repository.py.
- Added repository tests for persistence, recent/critical listing, deduplication, acknowledgements, corrupt storage, and compatibility output.
- Kept the work backend-only and did not alter broker permissions, RBAC, paper/live controls, or UI layouts.

## Repository Contract
The repository persists alerts with:
- alert_id
- timestamp
- severity
- event_type
- source
- message
- details
- acknowledged
- dedupe_key

Supported severities:
- INFO
- WARNING
- CRITICAL

Critical event types include:
- RUNTIME_FAILURE
- SUPERVISOR_RECOVERY
- BROKER_DISCONNECT
- TRADE_REJECTED
- RISK_GATE_BLOCK
- LIVE_MODE_BLOCKED
- DATA_UNAVAILABLE
- PNL_DRAWDOWN
- HEARTBEAT_STALE

## Compatibility
A compatibility adapter exposes a normalized payload shape for mobile/runtime Alert Centre consumers without changing UI layout.
