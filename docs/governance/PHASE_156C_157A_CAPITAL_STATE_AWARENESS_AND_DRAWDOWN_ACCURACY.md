# Phase 156C / 157A - Capital State Awareness and Drawdown Accuracy

## Scope

Improve runtime operational intelligence so missing broker balance, missing credentials, and account-readiness gaps are reported as capital-unavailable states instead of a misleading realized 100% drawdown event.

## Canonical Capital States

- CAPITAL_READY
- CAPITAL_UNAVAILABLE
- BROKER_BALANCE_UNAVAILABLE
- BROKER_CREDENTIALS_MISSING
- BROKER_CREDENTIALS_INVALID
- ACCOUNT_DATA_NOT_READY
- ZERO_FUNDED_ACCOUNT
- SIMULATED_CAPITAL_READY
- REAL_DRAWDOWN_ACTIVE

## Behavioral Guarantees

- Drawdown is marked NOT_COMPUTABLE when broker/account capital is unavailable.
- Drawdown percentage is computed only when capital state is tradeable and equity context is valid.
- Trade gate remains fail-closed for unavailable or unknown capital state.
- Live execution remains blocked when capital state is unavailable.
- No broker secrets are emitted in diagnostics payloads.

## Validation

- Added focused tests for unavailable capital, zero-funded accounts, simulated capital drawdown, real funded drawdown, unified trade gate blocking, unknown capital-state fail-closed behavior, and secret redaction.
