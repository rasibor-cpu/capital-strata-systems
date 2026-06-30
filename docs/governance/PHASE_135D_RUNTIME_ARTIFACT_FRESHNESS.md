# CSS Phase 135D - Runtime Artifact Freshness

## Purpose

Phase 135D makes runtime freshness explicit during long paper-validation runs. Overnight validation can remain `AMBER` when the runtime is healthy but an artifact timestamp, especially account state, is stale. This phase separates genuine broken pipeline conditions from expected idle-runtime conditions.

## Freshness Model

Critical artifacts:

- account state
- session state
- supervisor state

Optional artifacts:

- closed trade ledger
- portfolio snapshot
- runtime portfolio state
- runtime advisory snapshot
- portfolio decision
- validation summary

Missing critical artifacts are blockers. Missing optional artifacts are warnings.

## No-Recent-Trades Semantics

An old closed trade ledger does not imply a broken runtime when the supervisor is active and no trades have closed recently. The ledger state can be `NO_RECENT_TRADES`, which is advisory information, not a runtime-health blocker.

## Safe Refresh Rules

The freshness manager can safely refresh file timestamps for non-trading runtime artifacts when explicitly requested and the runtime is active. It does not alter monetary values, fabricate balances, rewrite trade results, or change execution authority.

## Safety

This phase does not enable broker execution, live trading, or executable advisory output. It preserves `advisory_only=true` and `execution_allowed=false`.

## Validation

Run:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_runtime_artifact_freshness.py tests/test_phase135d_runtime_health.py tests/test_phase135d_validation_readiness.py tests/test_phase135d_dashboard.py -q
```
