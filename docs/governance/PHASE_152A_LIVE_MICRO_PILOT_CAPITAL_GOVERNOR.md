# CSS Phase 152A Live Micro-Pilot Capital Governor

## Purpose

Phase 152A prepares CSS for a controlled live micro-pilot by adding a fail-closed capital governor around live order submission. This is a governance and safety-control phase. It does not enable live trading, does not start a live pilot, and does not modify broker execution permissions.

## Default Limits

- `pilot_enabled`: `false`
- `currency`: `CAD`
- `max_live_test_capital`: `20.00`
- `max_position_size`: `20.00`
- `max_concurrent_positions`: `1`
- `max_orders_per_session`: `10`
- `daily_loss_limit`: `2.00`
- `session_loss_limit`: `4.00`
- `allow_pyramiding`: `false`
- `allow_averaging_down`: `false`
- `require_manual_live_arming`: `true`
- `require_explicit_confirmation_word`: `EXECUTE`
- `auto_disarm_on_limit_breach`: `true`
- `fail_closed_if_config_missing`: `true`

## Enforcement Boundary

The governor applies only to live broker requests. Paper-mode and CSS paper broker requests are unchanged.

For live broker requests, existing controls remain authoritative:

- RBAC and SUPER_USER live requirements remain active.
- Live confirmation remains required.
- Live kill switch remains active.
- Canonical session, PnL, and margin checks remain active.
- TradeDecisionOrchestrator and ExecutionGate remain active.
- Unified Trade Gate, Margin Gate, and AntiBleedGuard are not bypassed.

The Phase 152A governor is a final pre-submission guard after existing downstream gates approve and before ledger/broker submission. A governor rejection returns `LIVE_MICRO_PILOT_REJECTED`, audits the reason, reports `live_order_sent: false`, and auto-disarms when configured.

## Operator Controls

Configuration, arming, and disarming require:

- `SUPER_USER` role
- Explicit confirmation word `EXECUTE`
- JSONL audit event

The controls cannot raise limits above the Phase 152A maximums. Unsafe configuration attempts fail loudly.

## Dashboard And API Visibility

Read-only surfaces expose Live Micro-Pilot Status through:

- Frontend contract section `live_micro_pilot`
- Dashboard runtime API `GET /api/v1/live-micro-pilot-status`
- Mobile API `GET /api/live-micro-pilot-status`
- Launcher API `GET /api/v1/live-micro-pilot-status`
- Mobile and launcher dashboard panels

Reported fields include pilot state, armed state, CAD cap, position limit, remaining capacity, open live positions, order count, loss limits, broker submission guard, operator control mode, and reporting summary.

## Live Validation Boundary

Phase 152A does not certify live broker operation. Live broker validation, operator rehearsal, and production operational certification remain separate required steps before any real-money deployment.
