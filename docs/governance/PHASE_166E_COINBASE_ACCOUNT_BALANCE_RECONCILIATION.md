# Phase 166E - Coinbase Account/Balance Reconciliation

## Purpose

Phase 166E reconciles Coinbase authenticated account, balance, buying-power,
equity, and margin evidence into one immutable canonical account snapshot.

This phase is read-only and fail-closed. It does not authorize execution, place
orders, cancel orders, arm broker execution, alter credentials, or change broker
permissions.

## Root Cause Addressed

Coinbase bootstrap and read-only validation could authenticate and retrieve
account evidence while runtime consumers still reported:

- `BROKER_BALANCE_UNAVAILABLE`
- `MARGIN_SNAPSHOT_UNAVAILABLE`

The ambiguity came from multiple lossy representations of the same broker read:
account summary, synthetic balance payloads, operational status, margin adapter
output, dashboard display values, and trade-gate input. In particular, the
dashboard margin path could build a display-only margin object and pass it to
the trade gate even though that object did not carry `buying_power`, causing the
gate to fail with `MARGIN_SNAPSHOT_UNAVAILABLE`.

## Canonical Account Snapshot

Phase 166E introduces `CanonicalAccountSnapshot` with the required account
readiness fields:

- `authenticated`
- `connected`
- `account_loaded`
- `portfolio_loaded`
- `balances_loaded`
- `equity_loaded`
- `buying_power_loaded`
- `margin_loaded`
- `market_data_loaded`
- `currency`
- `timestamp`
- `provenance`
- `failure_reason`
- `state_hash`

The snapshot also carries non-authorizing reconciliation metadata such as
account/portfolio identity, counts, balance timestamp, equity, cash, buying
power, available balance, margin available, required margin, and free margin.

## Provenance Rules

Every numeric account field has explicit provenance:

- `LIVE`
- `CACHE`
- `HISTORICAL`
- `SIMULATION`
- `UNAVAILABLE`
- `UNKNOWN`

When `balances_loaded=false`, all dependent live numeric fields are suppressed:

- equity
- cash
- balance
- buying power
- available balance
- margin available
- required margin
- free margin

Their provenance becomes `UNAVAILABLE`.

## Rejection Rules

The canonical snapshot and broker runtime validator reject contradictions,
including:

- live margin with unavailable balance
- positive buying power with unavailable balance
- equity loaded with missing account
- margin evidence from a different account
- portfolio mismatch
- balance timestamp mismatch
- consumer hash mismatch when reported by a consumer

Any contradiction feeds the existing canonical broker state fail-closed path.

## Consumer Model

Runtime, dashboard, frontend payloads, operational status, and trade-gate
evidence consume the canonical account snapshot when it is present. Legacy
fields remain for backward compatibility, but canonical snapshot values win.

If balances are unavailable:

- dashboard account values display unavailable
- margin values display unavailable
- trade gate remains blocked
- no live numeric values are shown beside an unavailable state

## Safety Guarantees

Phase 166E preserves:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `paper_only=true`
- `advisory_only=true`

It remains certification/reconciliation only. It never authorizes live trading.

## Relationship to Earlier Phases

Phase 166E extends the canonical broker readiness consolidation from Phases
166A through 166D. It does not replace broker authentication, endpoint
verification, execution firewall, R7 governance, RBAC, or NO-GO controls.

The canonical account snapshot is subordinate to the canonical broker runtime
state and feeds existing fail-closed validation.
