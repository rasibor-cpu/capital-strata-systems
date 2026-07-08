# Phase 156A - Live Broker Readiness Validation Framework

## Purpose

Phase 156A adds an advisory validation engine for checking whether a live broker
connection is ready for controlled read-only validation before any live testing
is considered.

The framework is strictly additive. It does not replace, weaken, bypass, or
authorize any existing R7 execution gates, RBAC controls, broker startup gates,
NO-GO logic, live execution firewall, execution boundary validation, broker
credential diagnostics, broker readiness framework, or Phase 153/155 controls.

## Validation Flow

The engine in `backend/runtime/live_broker_validation.py` runs a uniform
read-only validation sequence:

1. Credential validation uses the existing broker credential diagnostics module.
2. Bootstrap validation reuses `initialize_broker()`.
3. Authentication validation performs a read-only authentication probe.
4. Account validation checks broker-specific account evidence.
5. Market data validation checks one canonical quote.
6. Latency capture records authentication, account query, and market data timing.
7. Firewall validation verifies execution remains blocked and boundaries remain active.
8. Overall certification returns `GREEN` only when every stage passes.

Any failed stage returns `RED` with blocker reasons.

## Broker-Specific Read Checks

OANDA validation expects:

- account summary
- balance
- NAV
- margin available
- `EUR_USD` quote

Coinbase validation expects:

- accounts
- balances
- portfolio information
- `BTC-USD` quote

All broker checks are read-only. The framework has no order submission, order
cancellation, position mutation, arming, or live-trading enablement path.

## Safety Guarantees

Every Phase 156A report is advisory-only:

- `advisory_only` is always `true`
- `execution_allowed` is always `false`
- `live_trading_blocked` is always `true`
- broker failures fail closed to `RED`
- successful validation never authorizes trading
- JSON reports contain validation status and blockers, not secrets

The firewall validation deliberately verifies that live execution authority is
not granted and that the existing execution boundary rejects live mode with
simulated capital.

## Relationship To Existing Controls

Broker credential diagnostics remain the source of truth for credential
presence, redacted readiness, and credential failure classification.

Broker bootstrap remains the source of truth for adapter initialization through
`initialize_broker()`.

The broker readiness framework remains the canonical readiness snapshot model
for dashboard and parity views. Phase 156A does not replace it; it produces a
pre-test certification payload.

The execution firewall and live execution authority remain authoritative for
live trading controls. Phase 156A only verifies that those controls are still
blocking execution.

R7 governance, RBAC, startup gates, NO-GO controls, Phase 153 live-readiness
cleanup, and Phase 155 broker credential/read-only validation remain unchanged.

## Certification Meaning

`GREEN` means the broker passed the advisory read-only validation sequence.

`GREEN` does not mean live trading is approved. It does not arm execution, grant
operator authority, change broker mode, bypass NO-GO status, or satisfy R7
execution approval.

`RED` means at least one validation stage failed or was not safe to run.
