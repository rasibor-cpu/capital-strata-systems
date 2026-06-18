# Phase 105C-4 Regime Gate Telemetry Certification

## Scope

Phase 105C-4 hardens observability for the canonical Regime Gate runtime path in `engine/engine_loop.py`.

This phase is limited to audit, telemetry, diagnostics, and certification visibility. It does not change trading logic, strategy generation, broker execution, dashboard behavior, risk models, margin logic, credential handling, or `ExecutionGate` behavior.

## Implementation Summary

The engine loop now records a standardized regime gate decision payload each time the runtime Regime Gate is evaluated before `ExecutionGate`.

The runtime path remains:

```text
SignalEngine
-> existing FLAT signal handling
-> RegimeGate
-> ExecutionGate
```

If RegimeGate returns `BLOCK`, `ExecutionGate` remains bypassed. If RegimeGate returns `ALLOW`, the existing execution flow continues unchanged.

## Telemetry Structure

Regime Gate PASS telemetry uses:

```text
[REGIME GATE PASS] instrument=<instrument> gate=<gate_name>
```

Regime Gate BLOCK telemetry uses:

```text
[REGIME GATE BLOCK] instrument=<instrument> gate=<gate_name> reason=<reason>
```

## Diagnostics Structure

The engine loop records structured diagnostics under:

```text
diagnostics["regime_gate"]
```

The decision record contains:

```json
{
  "timestamp": "UTC ISO timestamp",
  "instrument": "instrument symbol",
  "gate_name": "regime_gate",
  "decision": "ALLOW or BLOCK",
  "reason": "decision reason",
  "bars_5m": "bar count used by the gate"
}
```

This structure is intended for future dashboard, certification, and runtime evidence visibility.

## Tests Executed

Targeted validation for this phase:

```text
.\.venv\Scripts\python.exe -m pytest tests\engine\test_engine_loop_regime_gate_wiring.py -q
.\.venv\Scripts\python.exe -m pytest tests\engine\test_regime_gate_registry.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_antibleed_guard_integration.py tests\test_margin_trade_gate.py tests\test_margin_trade_gate_enforcement_integration.py tests\engine\test_risk_governor.py -q
```

## Certification Findings

- Regime Gate ALLOW decisions are recorded.
- Regime Gate BLOCK decisions are recorded.
- Structured diagnostics are populated.
- PASS telemetry is emitted.
- BLOCK telemetry is emitted.
- `ExecutionGate` remains bypassed on RegimeGate BLOCK.
- `ExecutionGate` remains reachable on RegimeGate ALLOW.
- Existing SignalEngine FLAT behavior remains before RegimeGate evaluation.

## Boundaries Preserved

- No dashboard runtime integration was added.
- No broker execution logic was changed.
- No `ExecutionGate` method signatures were changed.
- No `RiskGovernor` behavior was changed.
- No margin logic was changed.
- No strategy generation logic was changed.
- No credential handling was changed.
- No additional registry gates were invoked.
