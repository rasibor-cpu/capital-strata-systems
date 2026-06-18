# ARP-002A AntiBleedGuard Remediation Report

## Original Audit Finding

ARP-001 verified audit finding B-01: `AntiBleedGuard` was implemented in the repository but was disconnected from the canonical execution path. The guard could evaluate low-edge, fee-bleed, rapid-loop, and micro-trade inefficiency risk, but no runtime caller invoked it before execution controls.

## Verification Result

Status: REMEDIATED FOR EXECUTIONGATE PRE-EXECUTION PATH

Verification confirmed that `backend/app/risk/anti_bleed_guard.py` defined `AntiBleedGuard`, but repository search found no active imports or callers outside documentation and audit artifacts before this phase.

The preferred long-form sequence:

```text
Trade candidate -> CSSUnifiedTradeGate -> AntiBleedGuard -> ExecutionGate -> Broker firewall
```

is not fully represented as a single canonical chain in the current repository. `CSSUnifiedTradeGate` and `ExecutionGate` remain separate controls in different runtime contexts. The closest safe canonical insertion point for this phase is therefore `ExecutionGate.evaluate_trade(...)`, before compounding, volatility sizing, drawdown scaling, risk governor validation, and any downstream broker firewall or router path.

## Files Reviewed

* `backend/app/risk/anti_bleed_guard.py`
* `engine/execution/execution_gate.py`
* `engine/engine_loop.py`
* `engine/adapters/super_execution_gate_adapter.py`
* `engine/testing/run_drawdown_stress.py`
* `backend/app/headless_guarded_entry.py`
* `backend/governance/css_unified_trade_gate.py`
* `backend/intelligence/trade_decision_orchestrator.py`
* `backend/app/brokers/live_readiness_certifier.py`
* `tests/engine/test_risk_governor.py`

## Files Changed

* `backend/app/risk/anti_bleed_guard.py`
* `engine/execution/execution_gate.py`
* `engine/engine_loop.py`
* `engine/adapters/super_execution_gate_adapter.py`
* `engine/testing/run_drawdown_stress.py`
* `backend/app/headless_guarded_entry.py`
* `tests/engine/test_risk_governor.py`
* `tests/test_antibleed_guard_integration.py`
* `certification/risk/RISK_CERTIFICATION_EVIDENCE_REGISTER.md`
* `docs/governance/ARP_002A_ANTIBLEEDGUARD_REMEDIATION_REPORT.md`

## Implementation Summary

`ExecutionGate` now invokes `AntiBleedGuard` as a pre-execution safety control before sizing and risk-governor evaluation. The guard requires:

* `instrument`
* `side`
* `notional`
* `expected_move_bps`
* `fee_bps`
* `spread_bps`
* `slippage_bps`

If any required AntiBleedGuard input is missing or invalid, the gate fails closed with a structured block:

```text
anti_bleed_guard:<reason>
```

The AntiBleedGuard decision is retained in `debug["anti_bleed_guard"]` so block reasons and economic inputs are auditable.

`AntiBleedGuard` now accepts an optional `state_file` parameter to support deterministic tests without writing to the default runtime artifact path. The default state file remains unchanged.

## Integration Point

Canonical remediation point:

```text
ExecutionGate.evaluate_trade(...)
  -> AntiBleedGuard.evaluate(...)
  -> CompoundingEngine
  -> VolatilityPositionSizer
  -> DrawdownScaler
  -> RiskGovernor.validate_trade(...)
```

This integrates AntiBleedGuard before broker execution without placing trades, calling broker APIs, changing strategy generation, modifying broker adapters, or changing dashboard behavior.

## Tests Added Or Updated

Added:

* `tests/test_antibleed_guard_integration.py`

Updated:

* `tests/engine/test_risk_governor.py`

Coverage includes:

* AntiBleedGuard is called in the `ExecutionGate` path.
* A valid candidate can proceed when AntiBleedGuard approves.
* A bleed-risk candidate is blocked.
* Missing AntiBleedGuard inputs fail closed.
* The block reason is auditable through the decision debug payload.
* Existing execution gate risk-governor path coverage still checks the precomputed risk governor path after AntiBleedGuard allows.

## Validation Results

Validation commands for this phase:

```text
.venv\Scripts\python.exe -m py_compile backend/app/risk/anti_bleed_guard.py engine/execution/execution_gate.py engine/engine_loop.py engine/adapters/super_execution_gate_adapter.py engine/testing/run_drawdown_stress.py backend/app/headless_guarded_entry.py
.venv\Scripts\python.exe -m pytest tests/test_antibleed_guard_integration.py tests/engine/test_risk_governor.py -q
```

Results are recorded in the final Codex delivery for this phase.

## Boundary Confirmation

This phase did not:

* modify `MarginTradeGate`
* modify `live_arm`
* modify `live_toggle`
* modify broker adapters
* modify dashboard behavior
* modify credential handling
* place trades
* call broker APIs
* enable live execution
* change trading strategy generation

## Remaining Risks

* `CSSUnifiedTradeGate` and `ExecutionGate` are still not a single end-to-end canonical chain. A later remediation phase should consolidate or explicitly document the authoritative ordering between candidate governance, execution sizing, broker firewall, and router controls.
* Runtime callers must provide meaningful AntiBleedGuard economics. Missing values now fail closed, but weak or placeholder economics can still reduce the quality of the anti-bleed decision.
* The dashboard has a separate local `CSSUnifiedTradeGate` implementation and was intentionally not modified in this phase.

## Certification Evidence Impact

This report provides captured remediation evidence for B-01. The risk certification evidence register references this report as evidence captured for AntiBleedGuard execution integration. It is not marked approved; Robert review remains required before merge or further remediation.
