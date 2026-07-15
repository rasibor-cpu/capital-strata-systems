# Phase 166A - Canonical Broker Readiness Consolidation

## Purpose

Phase 166A introduces a single immutable broker runtime state for read-only broker readiness reporting. It consolidates Coinbase live-readiness evidence that was previously computed separately by bootstrap, credential diagnostics, authentication tracing, readiness payloads, margin visibility, dashboards, and certification snapshots.

This phase is read-only, advisory, fail-closed, and does not authorize live execution.

## Architecture Reviewed

Reviewed broker readiness producers and consumers:

- `backend/app/brokers/credential_loader.py`
- `backend/app/brokers/broker_bootstrap.py`
- `backend/runtime/coinbase_authentication_trace.py`
- `backend/runtime/coinbase_live_adapter.py`
- `backend/runtime/coinbase_readiness.py`
- `backend/runtime/live_micro_pilot_governor.py`
- `backend/runtime/startup_summary.py`
- `backend/runtime/runtime_certification_snapshot.py`
- `backend/runtime/broker_credential_diagnostics.py`
- `dashboard/runtime/broker_credential_check.py`
- `dashboard/runtime/frontend_contract.py`
- `engine/risk/coinbase_margin_adapter.py`
- `launcher/templates/mobile_dashboard.html`
- `scripts/css_live_dashboard.py`

## Root Causes

Multiple subsystems independently interpreted broker readiness:

- Coinbase credentials could appear missing in one surface and present in another.
- Bootstrap self-test success could sit beside runtime authentication failure.
- Live account/balance unavailability could be masked by simulated margin fallback values.
- `.env.practice` values such as `COINBASE_TEST_ORDER_USD` could appear in live runtime views.
- Legacy `$1` Coinbase metadata was displayed beside the canonical CAD 20 micro-pilot governor without clearly stating that it was non-authoritative.

## Canonical State Model

Created:

- `backend/runtime/canonical_broker_runtime_state.py`
- `backend/runtime/canonical_broker_state_builder.py`
- `backend/runtime/canonical_broker_state_validator.py`
- `backend/runtime/canonical_broker_state_registry.py`
- `backend/runtime/canonical_broker_state_adapter.py`

The canonical model includes broker identity, mode, credential/authentication/connection/account/balance/buying-power/margin/market-data/product/order statuses, execution flags, pilot state, capital governor, readiness status, latency, HTTP evidence, error codes, environment evidence, source modules, timestamp, schema version, contradiction reasons, deterministic serialization, and stable hashing.

## Source Of Truth Precedence

Precedence is explicit in `SOURCE_PRECEDENCE`:

1. Current live broker response evidence
2. Current canonical authentication/account trace
3. Current broker adapter state
4. Current runtime registry state
5. Fresh cached evidence explicitly marked cached
6. Historical evidence for diagnostics only

Current failures override stale success. Bootstrap success does not override a current runtime authentication failure.

## Consumer Migration

Consumers now receive or expose `canonical_broker_runtime_state`:

- Coinbase readiness attaches canonical state and state hash.
- Startup summary renders canonical credential/auth/account/market statuses.
- Frontend broker contract exposes canonical state, hash, overall status, and contradiction reasons.
- Runtime certification snapshots include canonical broker state and deterministic hash.
- Live dashboard script attaches canonical state after operational validation updates.

Public legacy fields remain available for compatibility, but canonical state is the consolidated readiness evidence.

## Environment Validation

Coinbase startup variables are classified as `LIVE_ONLY`, `PRACTICE_ONLY`, `TEST_ONLY`, `SHARED`, `DEPRECATED`, or `UNKNOWN`.

Live mode fails closed when test/practice variables are present. Secret values are never printed; only presence, classification, source file, layer, current mode, severity, and redacted metadata are reported.

## Authentication Evidence

Canonical state preserves structured authentication evidence:

- HTTP status
- endpoint/category status
- Coinbase error code/message
- timeout/network/TLS/JWT/permission classifications
- clock-skew and credential validation evidence where present

Distinct failures such as `COINBASE_HTTP_401`, `COINBASE_HTTP_403`, `COINBASE_TIMEOUT`, `COINBASE_CLOCK_SKEW`, `COINBASE_INVALID_JWT`, `COINBASE_PERMISSION_DENIED`, `COINBASE_ACCOUNT_UNAVAILABLE`, `COINBASE_MARKET_DATA_ONLY`, and `COINBASE_BROKER_UNAVAILABLE` are not collapsed into generic unavailable state.

## Account, Balance, And Margin Reconciliation

Rules enforced:

- Market data PASS does not imply account readiness.
- Connection PASS does not imply authentication PASS.
- Live account/balance unavailable keeps buying power and margin unavailable.
- Positive simulated margin is rejected in live mode.
- Live margin fallback returns zero/unavailable evidence and fail-closed state.

## Legacy Compatibility

The legacy Coinbase `$1` path is classified as deprecated/display-only compatibility metadata. It does not override canonical live pilot limits. Authoritative values come from `backend/config/order_limit_config.py`, preserving CAD 20 pilot cap and fail-closed defaults.

## Contradiction Detection

Detected contradictions include:

- Missing credentials with authentication PASS
- Authentication FAIL with account READY
- Balance unavailable with positive live margin
- Execution allowed while live trading is blocked
- Broker execution armed while pilot is disarmed
- Live mode with practice/test contamination
- Order submission enabled in read-only scope
- Positive simulated live margin

Any contradiction produces fail-closed posture:

- `execution_allowed = false`
- `live_trading_blocked = true`
- `broker_execution_armed = false`

## Safety Posture

Phase 166A is advisory only. It never submits orders, cancels orders, routes trades, mutates credentials, arms execution, modifies broker state, or changes live trading authority.

Required posture remains:

- `execution_allowed = false`
- `live_trading_blocked = true`
- `broker_execution_armed = false`
- `advisory_only = true`

## Validation Evidence

Primary deterministic test suite:

- `tests/test_phase166a_canonical_broker_readiness.py`

Regression coverage includes Coinbase readiness, Coinbase live adapter, Phase 165 authentication evidence, Coinbase margin adapter, canonical order-limit config, broker diagnostics, Phase 156 certification, runtime smoke, dashboard/API/mobile, RC1 certification, and unified execution safety.

## Known Limitations

The canonical state is now exposed across key runtime/dashboard/certification surfaces. Some older modules still preserve legacy fields for compatibility. Future cleanup can remove direct legacy field consumers once all dashboard and automation clients consume `canonical_broker_runtime_state`.

## Remaining Prerequisites

Controlled live execution remains not authorized. A separate approved phase is required before any live pilot execution authority can be considered.
