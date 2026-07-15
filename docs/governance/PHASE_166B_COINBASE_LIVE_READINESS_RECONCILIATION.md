# Phase 166B - Coinbase Live Readiness Reconciliation

## Purpose

Phase 166B stabilizes the Coinbase live-readiness reporting path by forcing all runtime, dashboard, startup, certification, and diagnostic consumers to reconcile through the canonical broker runtime state.

This phase is read-only and fail-closed. It does not authorize trading, arm execution, submit orders, cancel orders, modify broker state, alter credentials, or change broker permissions.

## Architecture Reviewed

Phase 166B extends the Phase 166A canonical broker state spine:

- `backend/runtime/canonical_broker_runtime_state.py`
- `backend/runtime/canonical_broker_state_builder.py`
- `backend/runtime/canonical_broker_state_validator.py`
- `backend/runtime/canonical_broker_state_registry.py`
- `backend/runtime/coinbase_authentication_trace.py`
- `backend/runtime/coinbase_live_adapter.py`
- `backend/runtime/startup_summary.py`
- `dashboard/runtime/frontend_contract.py`

The canonical state remains the authority for broker readiness display and runtime certification evidence. Legacy payload fields may remain for backward compatibility, but consumers must prefer the canonical snapshot when present.

## Reconciliation Rules

The canonical account evidence object contains:

- `authenticated`
- `connected`
- `account_loaded`
- `balances_loaded`
- `buying_power_loaded`
- `margin_loaded`
- `products_loaded`
- `market_data_loaded`
- `equity_loaded`
- `account_type`
- `portfolio_loaded`

If balances are unavailable in live mode, dependent buying power, margin, and equity are unavailable. Synthetic, simulated, placeholder, stale, or historical live values cannot satisfy live account readiness.

Any contradiction produces:

- `overall_status=FAIL_CLOSED`
- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

Contradictions include:

- credentials unavailable with authentication pass
- authentication fail with account ready
- authentication fail with connection ready
- balance unavailable with buying power ready
- balance unavailable with margin ready
- positive simulated live margin
- live-mode environment contamination
- order submission enabled inside a read-only scope

## Environment Reconciliation

Coinbase environment variables are classified as:

- `LIVE`
- `PRACTICE`
- `TEST`
- `SANDBOX`
- `SHARED`
- `DEPRECATED`
- `UNKNOWN`

Each finding includes variable name, classification, source file, source layer, consumer, purpose, current mode, severity, and redaction status. Values are never emitted.

In live mode, practice, test, sandbox, demo, and truthy legacy execution variables fail closed. Deprecated display-only metadata remains warning-only when it does not grant execution authority.

## Authentication Diagnostics

Coinbase authentication traces preserve specific failure evidence for:

- HTTP 401, 403, 404
- timeout
- DNS
- TLS
- clock skew
- invalid JWT
- expired JWT
- bad key material
- permission denied
- missing portfolio, account, or balance access
- market-data-only credentials
- broker unavailable

These diagnostics are advisory evidence. They cannot bypass R7, RBAC, NO-GO, live execution firewall, pilot state, or broker execution gates.

## Startup And Dashboard Consistency

Startup display is restricted to canonical readiness fields:

- Credentials
- Authentication
- Connection
- Account
- Balances
- Buying Power
- Margin
- Market Data
- Products
- Readiness
- Overall Status
- Failure Reason
- Warnings
- State Hash

Dashboard payloads expose the canonical broker runtime state and canonical account evidence so desktop, mobile, API, launcher, runtime diagnostics, and certification displays can compare identical state hashes.

## Safety Guarantees

Phase 166B preserves:

- R7 execution gates
- RBAC
- NO-GO protections
- live execution firewall
- broker startup selection
- broker bootstrap
- broker credential diagnostics
- broker readiness framework
- Phase 156/165/166A advisory behavior

The phase provides live-readiness reconciliation only. It never certifies or grants execution authority.
