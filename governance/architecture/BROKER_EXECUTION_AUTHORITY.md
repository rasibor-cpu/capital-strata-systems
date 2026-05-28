# CSS Broker Execution Authority

## Purpose
Defines live/paper broker execution governance.

## Rules
1. Live mode must use real broker-validated balances.
2. Paper mode may use simulated balances only when explicitly selected.
3. No static capital value is allowed in live mode.
4. No simulated adapter may appear in a live execution path.
5. Broker credentials must never be committed.
6. Broker bootstrap must validate mode, credentials, broker readiness, and adapter availability.
7. Coinbase and OANDA remain current broker priorities.
8. Future IBKR-style expansion must remain broker-agnostic.
9. All broker execution must pass governance and audit checks before order submission.
