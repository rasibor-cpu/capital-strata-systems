# Phase 166C - Canonical Runtime State Final Reconciliation

## Purpose

Phase 166C is an RC1 pre-live stabilization pass for the broker runtime state. It eliminates remaining contradictory broker displays by requiring runtime consumers to use the canonical broker runtime state created in Phase 166A and hardened in Phase 166B.

This phase is read-only and fail-closed. It does not add broker features, authorize trading, arm execution, submit orders, cancel orders, change credentials, change broker permissions, change runtime databases, or alter deployment configuration.

## Canonical Connection Model

The canonical broker state separates:

- transport reachable
- authentication successful
- account accessible
- portfolio accessible
- balances loaded
- buying power loaded
- margin loaded
- market data loaded
- products loaded
- overall readiness

`transport_status` may show reachable transport evidence. `connection_status` may only pass when transport and authentication both pass. This prevents `CONNECTED YES` from appearing with `AUTH FAIL`.

## Margin Reconciliation

Margin values must carry provenance:

- `LIVE`
- `CACHE`
- `HISTORICAL`
- `SIMULATION`
- `UNAVAILABLE`
- `UNKNOWN`

If live balances are unavailable, live buying power, margin, and equity are unavailable unless the value is explicitly marked as `CACHE` or `HISTORICAL`. Synthetic live margin remains rejected.

## Bootstrap Reconciliation

Broker bootstrap self-test now reports canonical broker state instead of performing duplicate authentication, account, or market-data probes. Bootstrap initialization may still instantiate adapters, but readiness display must come from the canonical state object.

## Consumer Reconciliation

The following consumers are expected to display canonical state or canonical-adapted legacy fields:

- startup summary
- bootstrap diagnostics
- broker diagnostics
- margin dashboard
- live dashboard
- frontend contract
- runtime certification
- dashboard/API/mobile payloads
- RC1 reporting surfaces

Every surface should expose the same canonical state hash when it is rendering the same runtime snapshot.

## Failure Reasons

Failure reasons are structured and must not be displayed as `NONE` for failing broker readiness. Canonical examples include:

- `HTTP_401`
- `HTTP_403`
- `CLOCK_SKEW`
- `JWT_INVALID`
- `BALANCE_UNAVAILABLE`
- `ACCOUNT_UNAVAILABLE`
- `MARKET_DATA_ONLY`
- `ENVIRONMENT_CONTAMINATION`
- `BROKER_TIMEOUT`
- `DNS_FAILURE`
- `TLS_FAILURE`

## Safety Guarantees

Phase 166C preserves:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `paper_only=true`
- `advisory_only=true`

R7, RBAC, NO-GO protections, live execution firewall, broker startup gates, broker diagnostics, and all prior advisory-only broker readiness protections remain authoritative.
