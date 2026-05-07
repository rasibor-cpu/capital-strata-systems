# CSS Live Dashboard Migration Plan

Status: PCNRASS migration plan for gradually connecting
`scripts/css_live_dashboard.py` to the dashboard runtime architecture.

Do not use this plan as permission for a large rewrite. The production dashboard
must be migrated section by section, with compile/demo validation and rollback
points after each package.

## 1. Current Production Dashboard Map

Inspected file:

```text
scripts/css_live_dashboard.py
```

Current production dashboard responsibilities:

- Authentication and session startup.
- Global broker mode selection.
- Broker execution arming and broker selection.
- Engine mode selection.
- Session activity and defensive-mode checks.
- Broker status display.
- PnL/account reconciliation.
- Mark-to-market position tracking.
- Trade candidate selection.
- Pre-position profitability and unified trade gates.
- Paper/live execution boundary controls.
- Cycle-by-cycle console rendering.

## 2. Current Section Data Sources

### Account Section

Current sources:

- `pcnrass_account_state`
- `pcnrass_session_state`
- `pcnrass_asset_balances`
- `pnl_observer`
- `pnl_tracker`
- `capital_governor`
- OANDA account summary when selected and configured

Current output examples:

- Account balance
- Session realized PnL
- Session unrealized PnL
- Session equity
- Live equity
- Tracker equity
- Peak equity
- Drawdown

Runtime target:

- `account_payload`
- `broker_payload`
- `DashboardState.cash_balance`
- `DashboardState.total_equity`
- `last_scan_results["account_summary"]`

### PnL Section

Current sources:

- `mtm_engine`
- `pnl_observer`
- `pnl_tracker`
- `crypto_pnl`
- `fx_pnl`
- `options_pnl`
- `futures_pnl`
- `display_by_asset`
- `total_realized_pnl()`

Current output examples:

- Realized PnL
- Unrealized PnL
- Total equity PnL
- PnL reconciliation
- Observer/MTM mirror gap
- Asset realized/floating PnL

Runtime target:

- `positions_payload`
- `PnLSummaryBuilder`
- `PnLRenderContract`
- `PnLRenderer`

### Market Section

Current sources:

- `load_runtime_asset`
- `price_feed`
- `safe_load_runtime_asset`
- selected cycle candidates
- signal score and probability fields on candidate/position dictionaries

Current output examples:

- fetched candle messages
- profitability pass/block messages
- last trade status
- symbol-level candidate actions

Runtime target:

- `market_payload`
- `MarketStateBuilder`
- `MarketRenderContract`
- `MarketRenderer`

### Governance Section

Current sources:

- `SESSION_USER_CTX`
- `session_manager`
- `get_session_lock_state`
- `is_session_locked`
- role profile from `build_role_profile`
- `CSSUnifiedTradeGate`
- RBAC audit events

Current output examples:

- session active
- defensive mode active
- session lock reason
- allowed engine modes
- paper/live execute permissions
- unified gate block messages

Runtime target:

- `governance_payload`
- `GovernanceStateBuilder`
- `GovernanceRenderContract`
- `GovernanceRenderer`

### Risk Section

Current sources:

- `pnl_tracker.max_drawdown`
- hard position limits
- asset caps
- per-cycle new-position caps
- `AdaptiveConcurrencyEnvelopeController`
- `ClusterSaturationRiskGovernor`
- `LockedProfitLedger`
- defensive exposure reduction

Current output examples:

- open positions
- open by asset
- adaptive position limit
- defensive reductions
- total defensive reduction exits
- cluster saturation

Runtime target:

- `risk_payload`
- `RiskSummaryBuilder`
- `RiskRenderContract`
- `RiskRenderer`

### Execution Section

Current sources:

- `BROKER_EXECUTION_ARMED`
- `SELECTED_BROKER`
- `SELECTED_BROKER_MODE`
- `attempt_oanda_fx_execution`
- `attempt_coinbase_crypto_execution`
- `coinbase_live_orders_enabled`
- `evaluate_coinbase_live_gate`
- `approve_trade_before_register`
- `capital_governor`

Current output examples:

- broker execution status
- selected broker
- broker mode
- execution scope
- broker open/manual-review messages
- pass/block gate messages

Runtime target:

- `execution_payload`
- `ExecutionSummaryBuilder`
- `ExecutionRenderContract`
- `ExecutionRenderer`

## 3. Migration Order

Recommended order:

1. Create read-only payload extraction helpers beside the live dashboard.
2. Add a no-output runtime adapter that builds payload dictionaries from existing
   live dashboard variables.
3. Validate adapter payloads with `DashboardHydrationCoordinator` without
   replacing any live dashboard print sections.
4. Add diagnostics-only comparison output gated behind an environment flag.
5. Route one low-risk section through runtime rendering in shadow mode.
6. Migrate account summary display after shadow output matches current values.
7. Migrate PnL display after account migration is stable.
8. Migrate governance/session display after PnL migration is stable.
9. Migrate broker/execution display last.

Do not start broker/execution migration before account, PnL, and governance
runtime sections are stable in the live dashboard.

## 4. Safest Adapter/Shim Sequence

### Adapter 1: Runtime Payload Snapshot

Create a helper module, not a dashboard rewrite:

```text
dashboard/runtime/live_dashboard_payload_adapter.py
```

Purpose:

- Accept primitive values from `scripts/css_live_dashboard.py`.
- Return normalized payload dictionaries.
- Avoid imports from live broker adapters.
- Avoid execution side effects.

### Adapter 2: Shadow Hydration Check

Add an optional call site in `scripts/css_live_dashboard.py` only after Adapter 1
is compile-clean and tested in isolation.

Rules:

- Environment gated.
- Default off.
- No replacement of current print output.
- No broker calls.
- No trade execution.

Suggested environment flag:

```text
CSS_RUNTIME_SHADOW_DASHBOARD=true
```

### Adapter 3: Section-Level Runtime Rendering

Migrate one section at a time.

First candidate:

- Account summary

Later candidates:

- PnL summary
- Governance/session summary
- Risk summary
- Execution summary

## 5. Rollback Strategy

Each migration package must be independently revertible.

Rollback checkpoints:

- Adapter module created.
- Shadow hydration enabled but output disabled by default.
- First runtime-rendered section gated.
- First runtime-rendered section enabled by default.

Rollback rule:

- If live dashboard compile fails, revert the current package.
- If sign-in/session/mode selection changes unexpectedly, revert immediately.
- If broker execution behavior changes, revert immediately.
- If paper dashboard output loses key visibility, revert immediately.

## 6. Regression Risks

High-risk areas:

- Auth/sign-in/password change flow.
- Session persistence and session expiration behavior.
- Global broker mode selection.
- Broker arming.
- OANDA/Coinbase selection and status display.
- Live execution blocking rules.
- PnL authority and observer mirror logic.
- Mark-to-market lifecycle.
- Open position caps and per-asset caps.
- Defensive mode and forced reduction logic.
- Manual cycle pause behavior.

Do not alter these while adding read-only runtime adapters.

## 7. Files Not To Touch Yet

Avoid production rewrites in:

```text
scripts/css_live_dashboard.py
```

Do not modify live broker/execution modules unless a later package explicitly
requires it and has its own validation plan.

Do not modify:

- credential files
- live broker keys
- `.env`
- `CSS-CLAUDE`

## 8. Validation Commands

Core runtime compile:

```powershell
.\.venv\Scripts\python.exe -m py_compile dashboard\runtime\runtime_bootstrap.py dashboard\runtime\dashboard_hydration_coordinator.py dashboard\runtime\dashboard_state_factory.py dashboard\runtime\dashboard_renderer.py dashboard\runtime\demo_runtime_runner.py
```

Runtime demo:

```powershell
.\.venv\Scripts\python.exe -m dashboard.runtime.demo_runtime_runner
```

Runtime smoke:

```powershell
.\.venv\Scripts\python.exe -m dashboard.runtime.runtime_smoke_test
```

Live dashboard compile before any live dashboard adapter package:

```powershell
.\.venv\Scripts\python.exe -m py_compile scripts\css_live_dashboard.py
```

Git status:

```powershell
git status --short
```

## 9. Next Recommended Package

Create:

```text
dashboard/runtime/live_dashboard_payload_adapter.py
```

Initial scope:

- Pure functions only.
- Accept explicit primitive values and dictionaries.
- Return payload dictionaries for account, positions, market, governance, risk,
  execution, session, and diagnostics.
- No import of `scripts/css_live_dashboard.py`.
- No broker calls.
- No rendering.

This prepares live dashboard migration without touching the production dashboard.
