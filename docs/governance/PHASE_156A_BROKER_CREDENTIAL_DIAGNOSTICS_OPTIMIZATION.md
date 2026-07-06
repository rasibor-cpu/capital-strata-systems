# Phase 156A - Broker Credential Diagnostics Optimization

## Scope

Refine the broker credential diagnostics contract so launcher, dashboard, and API surfaces can display a stable readiness view without weakening fail-closed behavior.

## Goals

- Expose canonical broker identity and readiness status.
- Preserve secret redaction and read-only safety.
- Surface safe remediation hints for missing broker credentials.
- Keep live trading blocked unless the existing execution authority path explicitly allows it.

## Validation

- Add diagnostics coverage for Coinbase, OANDA, and unknown brokers.
- Verify valid-looking credential sets are reported as ready.
- Confirm no secret values appear in diagnostic payloads.
