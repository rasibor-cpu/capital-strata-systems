# Phase 110B: Dashboard Gate Adapter Migration

## Objective
Migrate the legacy dashboard trade-gate pre-checks directly into the canonical backend adapter (`CSSGateDashboardAdapter`). This ensures `scripts/css_live_dashboard.py` relies solely on the adapter for all governance without altering its frozen output shape, taking a significant step toward unifying the execution pipeline under `backend/governance/css_unified_trade_gate.py`.

## Actions Taken
1. **Adapter Extension**: Injected `_evaluate_legacy_dashboard_rules` into `CSSGateDashboardAdapter` to ingest, translate, and evaluate legacy session contexts, RBAC permissions, and asset-class limits originally hardcoded in the dashboard file.
2. **Dashboard Refactor**: Removed the large `if/elif` governance block in `css_live_dashboard.py:approve_trade_before_register`. The function now immediately defers decision-making to the `css_unified_trade_gate.approve_trade()` entry point.
3. **Freeze Test Alignment**: Updated `tests/test_dashboard_trade_gate_freeze.py` to assert that legacy rules (like missing paper trading permissions) properly fail through the adapter interface.

## Mismatch & Retirement Status Table

| Legacy Behavior | Status | Notes |
|---|---|---|
| Session Active Checks | **Resolved** | Delegated fully to `CSSGateDashboardAdapter` |
| Session Lock Checks | **Resolved** | Evaluated via `is_session_locked` context passed to Adapter |
| Unsupported Asset Classes | **Resolved** | Delegated fully to `CSSGateDashboardAdapter` |
| Live/Paper RBAC Flags | **Resolved** | Delegated fully to `CSSGateDashboardAdapter` |
| "SAFE" Engine Mode Live Block | **Resolved** | Delegated fully to `CSSGateDashboardAdapter` |
| Probability Override Clamping | **Remaining Unmapped** | The adapter still artificially clamps `probability` up to thresholds. This prevents canonical rejection. |
| Role "TRADER" vs Flags | **Remaining Unmapped** | Adapter evaluates both pure string roles (backend) and legacy boolean dictionary flags (frontend). |

## Deferred Retirement Items
- **Adapter Clamping**: The adapter's `_dashboard_compatible_probability` hack must be retired in future phases to allow the backend `PropTradingGovernor` to correctly enforce probability thresholds.
- **`is_session_locked` Context**: The adapter still accepts a boolean `is_session_locked` from the frontend instead of tracking session locking autonomously via database or redis limits.
