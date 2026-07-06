# Phase 154B - Broker Parity Validation

Status: Implemented for review.

## Objective

Phase 154B validates that Coinbase and OANDA behave identically under the canonical Phase 154A Broker Readiness Framework.

## Scope

`backend/runtime/broker_parity_validator.py` compares Coinbase and OANDA readiness snapshots using the same canonical comparable fields. Broker identity fields such as broker name/type are retained in the report, but execution authority is evaluated only from canonical readiness and shared safety evidence.

The validator checks:

- missing credentials fail closed for both brokers
- authentication failure fails closed for both brokers
- broker execution disabled produces matching blocked authority decisions
- pilot disarmed produces matching blocked authority decisions
- authority and fail-closed parity remain true across the scenarios
- mismatched readiness fields are reported for operator review

## Dashboard And API Visibility

Phase 154B publishes a read-only broker parity report through dashboard/frontend/launcher surfaces. The report includes Coinbase readiness, OANDA readiness, parity status, mismatched fields, authority parity, and fail-closed parity.

## Safety Boundary

Phase 154B does not enable live trading, arm broker execution, arm the Live Micro-Pilot, or submit broker orders. Unified Trade Gate, Margin Gate, AntiBleedGuard, RBAC, Kill Switch, Phase 152A CAD20 Governor, and Live Execution Authority remain authoritative and fail-closed.
