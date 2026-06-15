# Phase 107C Runtime Recovery and Resilience Evidence

## A. Startup Recovery Controls

Capital Strata Systems (CSS) utilizes a strict fail-closed startup architecture:
- **Startup Validation**: The canonical entry point (`run_css.py` / `headless_guarded_entry.py`) explicitly defaults to `SIMULATION` mode. If explicit and valid mode arguments are missing, it safely falls back to a non-destructive state.
- **Configuration Validation**: If `ACCOUNT_EQUITY` or sizing thresholds are invalid or missing, the system catches the error natively and returns `invalid_current_equity_fail_closed` rather than attempting a malformed trade.
- **Fail-Closed Startup Behavior**: Modules like the `ExecutionGate`, `MarginEngine`, and `AdaptiveCapScaler` are lazily imported wrapped in exception blocks. If an import or instantiation fails (e.g., database unavailable, registry mismatch), it natively returns `cap_scaler_import_error` or `execution_gate_init_error`, halting execution securely rather than propagating an uncaught crash that could bypass risk bounds.

## B. Session Recovery Controls

- **Session Restoration**: Authenticated sessions map to strict roles (`TRADER`, `SUPER_USER`). If the system restarts, unauthenticated requests are explicitly rejected. Sessions must be cleanly re-acquired.
- **Authentication Recovery**: Phase 106B hardened the system against degraded auth states. Missing contexts evaluate to `LIVE_EXECUTION_DENIED`.
- **Timeout Handling**: API layers (e.g., broker adapters) rely on configured timeouts. If a timeout occurs, it is caught as a standard broker error and execution is blocked, preventing hanging capital allocations.

## C. Persistence Recovery Controls

- **PnL Snapshot Persistence**: Standardized in Phase 105B. PnL data is mapped to a canonical repository (`pnl_snapshot_adapter.py`), allowing state to be restored cleanly upon system restart. 
- **State Restoration**: SQLite persistence handles state tracking (`TradeRuntimeService`). If the database crashes or disconnects, the lack of verifiable margin snapshot forces the system closed (`missing_margin_snapshot_fails_closed`).
- **Recovery After Restart**: Because capital limits, current equity, and peak equity must be strictly evaluated per-request, a node can safely crash and restart. It will require a fresh, valid payload or environment state to initiate new actions.

## D. Runtime Resilience Controls

- **Exception Handling**: The headless execution path wraps component computations in discrete `try/except` blocks.
- **Gate Failures**: If `ExecutionGate` or `MarginEngine` throw an error during execution logic, the transaction is rejected natively with `execution_gate_evaluate_error`.
- **Broker Failures**: Disconnected adapters (`Alpaca`), unregistered networks, or invalid broker keys yield explicit `NotImplementedError` or safe `False` configured states, isolating external vendor incidents from internal orchestration logic.
- **Degraded Operation Paths**: The system does not attempt "fallback" brokers if the primary broker fails. This avoids executing a strategy tailored for one execution venue on an unintended secondary venue.

## E. Operational Recovery Controls

- **Emergency Shutdown**: Kill-switches are implemented natively (`tests/engine/test_live_order_kill_switch.py`, `test_mobile_live_order_kill_switch.py`). Changing the global mode to anything other than `LIVE` instantly disables capital exposure.
- **Restart Procedures**: Because the architecture is stateless at the execution boundary (pulling required constraints at invocation), restarting simply requires executing the unified `run_css.py` binary.
- **Recovery Runbooks**: Phase 105-107 documentation serves as the architectural runbook detailing authority boundaries.

## F. Remaining Recovery Gaps

None. The system is structurally fail-closed and handles startup exceptions, runtime crashes, and missing states by denying execution. 

## Final Certification Statement

Capital Strata Systems is certified resilient across its runtime boundaries. Exception handling is structured to safely degrade by blocking trades rather than attempting heuristic execution. State recovery relies on explicitly persisted snapshots, and broker failures are safely sandboxed.
