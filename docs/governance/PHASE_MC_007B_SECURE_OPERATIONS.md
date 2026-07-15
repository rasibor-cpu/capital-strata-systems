# Phase MC-007B - Mission Control Secure Operations

## Purpose

Phase MC-007B adds a secure operations visibility layer to CSS Mission Control.
It exposes role, approval, configuration, broker registry, feature flag, audit,
change history, rollback planning, and governance posture panels.

The phase is read-only. It does not add write routes, operational buttons,
runtime mutation hooks, broker mutation hooks, or trading authority.

## Added Consoles

- RBAC console
- Operator console
- Approval workflow console
- Configuration console
- Broker registry console
- Feature flag console
- Audit center
- Change history console
- Rollback planner
- Governance summary

Each console includes source, provenance, generated timestamp, freshness,
runtime id, and state hash when available.

## Data Flow

1. Existing runtime/dashboard payloads are normalized by the frontend contract.
2. Mission Control builds its canonical state contract.
3. Existing permissions, governance, broker, configuration, audit, certification,
   and safety sections are projected into MC-007B consoles.
4. Source consistency validates hash alignment across the secure operations
   panels.

MC-007B does not duplicate RBAC, approval, broker, or certification logic. It
adapts existing state for display.

## Fail-Closed Rules

Mission Control fails closed when:

- permissions are missing or invalid
- source consistency fails
- runtime identity mismatches
- state hashes diverge
- audit evidence is malformed
- configuration evidence is malformed
- non-finite values appear
- unsafe safety flags appear
- protected material appears in payloads

Offline runtime state produces fail-closed control-plane panels.

## Safety Guarantees

MC-007B preserves:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

MC-007B never submits trades, cancels trades, arms trading, enables live trading,
edits broker connection material, overrides risk controls, overrides
AntiBleedGuard, overrides committee decisions, or disables certification.

## Governance Relationship

MC-007B remains subordinate to:

- existing RBAC
- R7 governance
- broker startup and readiness gates
- certification
- live firewall protections
- execution boundary validation
- no-go protections

It is an institutional visibility plane only.
