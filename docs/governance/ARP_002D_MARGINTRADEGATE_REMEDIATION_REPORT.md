# ARP-002D MarginTradeGate Remediation Report

## Original Audit Finding

ARP-001 verified audit finding B-04: `MarginTradeGate` existed but was not enforced in the canonical trade path. It was visible through dashboard display logic, but no pre-execution authority could block a trade based on margin state.

## Verification Result

Status: REMEDIATED

Verification confirmed:

* `engine/risk/margin_trade_gate.py` defines `MarginTradeGate` and `MarginTradeGateDecision`.
* `MarginTradeGate.evaluate(...)` consumes an existing `MarginSnapshot` from `engine/risk/margin_engine.py`.
* The gate returns deterministic decisions: `ALLOW`, `MONITOR`, `RESTRICT_NEW_RISK`, `DEFENSIVE_ONLY`, or `BLOCK`.
* Before ARP-002D, the only active reference was dashboard visibility in `scripts/css_live_dashboard.py`; the canonical `ExecutionGate` path did not enforce margin decisions.

## Files Reviewed

* `engine/risk/margin_trade_gate.py`
* `engine/risk/margin_engine.py`
* `engine/execution/execution_gate.py`
* `engine/engine_loop.py`
* `engine/adapters/super_execution_gate_adapter.py`
* `engine/testing/run_drawdown_stress.py`
* `backend/app/headless_guarded_entry.py`
* `tests/test_margin_trade_gate.py`
* `tests/test_antibleed_guard_integration.py`
* `tests/engine/test_risk_governor.py`

## Files Changed

* `engine/execution/execution_gate.py`
* `engine/engine_loop.py`
* `engine/adapters/super_execution_gate_adapter.py`
* `engine/testing/run_drawdown_stress.py`
* `backend/app/headless_guarded_entry.py`
* `tests/test_margin_trade_gate_enforcement_integration.py`
* `tests/test_antibleed_guard_integration.py`
* `tests/engine/test_risk_governor.py`
* `docs/governance/ARP_002D_MARGINTRADEGATE_REMEDIATION_REPORT.md`
* `certification/risk/RISK_CERTIFICATION_EVIDENCE_REGISTER.md`
* `certification/margin/MARGIN_CERTIFICATION_EVIDENCE_REGISTER.md`

## Canonical Insertion Point

The safest insertion point is:

```text
engine/execution/execution_gate.py::ExecutionGate.evaluate_trade(...)
```

This is the same pre-execution authority used by ARP-002A for AntiBleedGuard integration. It allows margin enforcement to run before sizing, risk-governor validation, execution routing, and broker firewall behavior.

## Enforcement Sequence

The effective sequence is now:

```text
Trade candidate
  -> AntiBleedGuard
  -> MarginTradeGate
  -> Compounding / volatility / drawdown sizing
  -> RiskGovernor validation
  -> downstream execution / broker firewall controls
```

The requested preferred chain includes `CSSUnifiedTradeGate` before AntiBleedGuard. In the current repository, `CSSUnifiedTradeGate` and `ExecutionGate` remain separate runtime authorities. ARP-002D therefore integrates margin into the closest enforced canonical pre-execution path without changing dashboard behavior, broker adapters, strategy generation, or unrelated governance controls.

## Enforcement Behavior

`ExecutionGate.evaluate_trade(...)` now requires a precomputed `MarginSnapshot`:

* Missing margin snapshot fails closed with `margin_trade_gate:BLOCK:missing_margin_snapshot`.
* `GREEN/NORMAL` and `YELLOW/MONITOR` can proceed.
* `ORANGE/RESTRICT_NEW_RISK` blocks new exposure.
* `RED/DEFENSIVE_ONLY` blocks new exposure.
* `BLACK/CRITICAL_BLOCK` blocks new exposure.
* `LIVE` with `UNKNOWN` margin state fails closed through existing `MarginTradeGate` behavior.

The margin decision is recorded in:

```text
debug["margin_trade_gate"]
```

This preserves an auditable reason, state, escalation state, utilization, and control name.

## Caller Wiring

* `engine/engine_loop.py` supplies an explicit simulated margin snapshot for simulation/paper operation.
* `engine/adapters/super_execution_gate_adapter.py` forwards a caller-provided margin snapshot and broker mode.
* `backend/app/headless_guarded_entry.py` builds a snapshot from request or environment margin values. Paper/simulation defaults to a deterministic simulated snapshot; live mode without margin data becomes `UNKNOWN` and blocks.
* `engine/testing/run_drawdown_stress.py` supplies explicit simulated margin.

No broker margin retrieval was added in this phase.

## Tests Added Or Updated

Added:

* `tests/test_margin_trade_gate_enforcement_integration.py`

Updated:

* `tests/test_antibleed_guard_integration.py`
* `tests/engine/test_risk_governor.py`

Coverage includes:

* MarginTradeGate is called in the `ExecutionGate` path.
* Valid GREEN margin allows the execution gate to continue.
* ORANGE margin blocks before risk governor validation.
* Missing margin snapshot fails closed.
* LIVE UNKNOWN margin fails closed.
* Margin block reasons are auditable.
* Existing AntiBleedGuard and ExecutionGate tests still pass.
* Existing margin stack tests still pass.

## Validation Results

Validation commands for this phase:

```text
.venv\Scripts\python.exe -m py_compile engine\execution\execution_gate.py engine\engine_loop.py engine\adapters\super_execution_gate_adapter.py engine\testing\run_drawdown_stress.py backend\app\headless_guarded_entry.py tests\test_margin_trade_gate_enforcement_integration.py tests\test_antibleed_guard_integration.py tests\engine\test_risk_governor.py
.venv\Scripts\python.exe -m pytest tests\test_margin_trade_gate.py tests\test_margin_trade_gate_enforcement_integration.py tests\test_antibleed_guard_integration.py tests\engine\test_risk_governor.py -q
.venv\Scripts\python.exe -m pytest tests\test_margin_engine.py tests\test_broker_margin_contract.py tests\test_oanda_margin_adapter.py tests\test_coinbase_margin_adapter.py tests\test_margin_trade_gate.py -q
```

Results are recorded in the final Codex delivery for this phase.

## Boundary Confirmation

This phase did not:

* modify AntiBleedGuard logic
* modify live_toggle RBAC logic
* modify live_arm logic
* modify broker adapters
* modify dashboard behavior
* modify credential handling
* modify strategy generation
* modify execution cost logic
* fetch broker margin data
* place trades
* call broker APIs
* enable live execution by default

## Remaining Risks

* `CSSUnifiedTradeGate` and `ExecutionGate` remain separate authorities. A later consolidation phase should define the full canonical ordering and remove ambiguity between candidate governance and execution governance.
* Live margin enforcement depends on callers supplying broker-authoritative margin data. If live margin data is missing, this remediation fails closed.
* Full production certification still requires retained live broker margin evidence and Robert review.

## Certification Impact

ARP-002D provides captured evidence that margin trade gate decisions are now enforced in the pre-execution `ExecutionGate` path. Risk and margin certification evidence registers reference this report. No evidence is marked approved; Robert review remains required before merge or further remediation.
