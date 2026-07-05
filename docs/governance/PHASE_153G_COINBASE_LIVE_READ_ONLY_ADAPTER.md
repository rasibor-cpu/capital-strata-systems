# Phase 153G - Coinbase Live Read-Only Adapter

Status: Implemented for review.

## Objective

Phase 153G adds the canonical Coinbase LIVE read-only adapter used for pre-live broker validation evidence. This phase does not enable live trading, broker execution, live micro-pilot arming, or order submission.

## Adapter Boundary

`backend/runtime/coinbase_live_adapter.py` exposes only read-only operations:

- authentication status
- account retrieval
- balances
- products
- server time
- ticker / market data
- connection status

The adapter does not expose order placement, order cancellation, order modification, or broker execution methods. Runtime status payloads always publish:

- `broker_execution_status = DISABLED`
- `can_live_execute = False`
- `live_order_permission = False`
- `execution_allowed = False`
- `live_micro_pilot_state = DISARMED`
- `broker_guard = REJECT_BEFORE_BROKER`

## Credential Safety

Credential diagnostics report only `PRESENT` / `MISSING` status and missing credential names. API keys, private keys, secrets, signatures, tokens, passphrases, and raw credential values are never published to dashboard/API payloads.

## Broker Health

Coinbase broker health transitions are explicit:

1. `UNKNOWN`
2. `CONNECTING`
3. `CONNECTED`
4. `HEALTHY`

`HEALTHY` is reported only after successful authenticated read-only account or balance communication.

## Drawdown Correction

If no broker balance is available, read-only status reports:

- `drawdown_status = UNKNOWN`
- `drawdown_reason = Broker balance unavailable`

CSS must not infer or report a 100% drawdown from absent broker balance evidence.

## Dashboard And API Visibility

Read-only broker evidence is propagated through canonical runtime artifacts, the frontend contract, the mobile launcher, and the read-only broker status API. Operator-visible fields include broker, connection/authentication status, credential status, last broker sync, account equity, cash, buying power, available balance, products loaded, market data status, execution scope, broker execution status, live micro-pilot state, and broker guard.

## Safety Boundary

Phase 153G preserves all existing live safety controls:

- Unified Trade Gate
- Margin Gate
- AntiBleedGuard
- RBAC
- Kill Switch
- Live Readiness Certification
- Broker Execution Controls
- Phase 152A CAD 20 Live Micro-Pilot Governor

This phase is evidence collection only. Live broker validation and any future live micro-pilot remain separate governed operational steps.
