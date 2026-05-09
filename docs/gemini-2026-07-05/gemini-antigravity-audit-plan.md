# Capital Strata Systems (CSS) PCNRASS Implementation Plan

This plan outlines the execution of the 10 core tasks (T01-T10) identified in the institutional architecture audit, alongside the High Priority PnL Authority fix (HP-3), Medium Priority Test Migration (MP-3), and the Live Dashboard Migration phases (M2-M5). 

All changes will be executed following the strict **Please Confirm No Regression And Stable State (PCNRASS)** discipline. I will activate the local `.venv` before running any test or compilation checks.

## User Review Required

> [!IMPORTANT]  
> Please review this finalized plan. Once approved, I will begin execution and track progress in `task.md`. I will make atomic `git commits` for each phase using the environment's Git configuration.

## Proposed Changes

### Phase 1: Root Hygiene (T09, T10)
- **Delete Ghost Files:** Run `git rm` on zero-byte root fragments (`bool`, `str`, `int`, `0`, `16`, `css_audit_package.zip`, etc.).
- **Archive Scripts:** Move all 27 `build_*.py` and `temp_*.py` patch scripts to `archive/patches/` using `git mv`.
- **Validation:** `git status` check, ensure no broken imports.

### Phase 2: Safe Additive Testing (T05, T06)
- **New Test Files:** Create tests for `PnLSummaryBuilder`, `PositionStateBuilder`, `RiskGovernor`, and `ExecutionCostEngine`.
- **Validation:** Execute `pytest` using the `.venv` Python interpreter.

### Phase 3: Minimal Single-Line Fixes (T02, T07)
#### [MODIFY] `engine/execution/live_state.py`
- Update the hardcoded `os.path.join("audit", "live_state.json")` path. As best practice, it will prioritize the `CSS_LIVE_STATE_PATH` environment variable, with `Path(__file__).resolve().parents[3] / "audit" / "live_state.json"` acting as the robust default fallback.

#### [MODIFY] `engine/execution/execution_gate.py`
- Inject a `WARN` logging line whenever the volatility sizing fallback mechanism is invoked to surface API drift.

### Phase 4: Additive Bridge & Refactoring (T01, T03, HP-3, MP-3)
#### [MODIFY] `dashboard/runtime/dashboard_state.py`
- Add a `resolved_mode()` method to synchronize `live_or_paper` and `broker_mode`.
- Add a serialization-safe `to_dict()` method.

#### [NEW] `dashboard/runtime/_utils.py`
- Extract and centralize `safe_float()` and `safe_int()`.

#### [MODIFY] Multiple Files
- Refactor `PositionStateBuilder`, `PnLSummaryBuilder`, and `live_dashboard_payload_adapter.py` to use `dashboard/runtime/_utils.py`.
- Define `CANONICAL_PNL_SOURCE = "engine.ledger.pnl_engine.PnLEngine"` in `engine/ledger/__init__.py`.
- Update `PnLSummaryBuilder` documentation to clarify it is a presentation layer, not the accounting authority.
- **Test Migration:** Move root-level test files (e.g. `test_regime_gate.py`) to the `tests/` directory.

### Phase 5: Engine Wiring (T04, T08)
#### [MODIFY] `engine/ledger/pnl_engine.py`
- Add an optional `cost_engine: ExecutionCostEngine | None = None` parameter to the constructor.
- Subtract friction costs on realized exits if the engine is bound.

#### [MODIFY] `engine/brokers/base_broker.py`
- Validate that the `resolved_mode()` properly gates orders.

### Phase 6: Live Dashboard Migration Prep (M2-M5)
#### [NEW] `dashboard/runtime/api_bridge.py`
- Build a FastAPI wrapper around `DashboardRuntimeBootstrap` pointing at `/api/v1/dashboard-state`.

#### [MODIFY] `scripts/css_live_dashboard.py` / `css_live_dashboard_v5.py`
- Incrementally update panel callbacks (starting with PnL) to consume the `DashboardState` via the hydration coordinator rather than legacy sources.

## Verification Plan

### Automated Tests
- For each phase, run corresponding unit tests and compilation checks utilizing `.venv\Scripts\python.exe -m pytest` and `python -m py_compile`.
- **Sprint Protections:** Proactively run sprint smoke tests (`css_sign_on_smoke_test.py` and `mobile_smoke_test.py`) alongside others to strictly verify that no collateral damage has occurred to the ongoing auth/mobile sprint.

### Manual Verification
- Validate the new `/api/v1/dashboard-state` endpoint returns valid JSON payload.
- Ensure all phases compile successfully prior to their git commit.
