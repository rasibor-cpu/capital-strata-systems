# Phase RC1-OPS-R1 - Runtime Smoke PnL Reconciliation Remediation

## Purpose

Phase RC1-OPS-R1 remediates the RC1-OPS runtime smoke blocker:

```text
dashboard.runtime.runtime_smoke_test
PnL summary unrealized mismatch
```

This remediation is targeted, paper-only, and advisory-only. It does not modify broker adapters, credentials, execution routing, order submission, order cancellation, execution arming, runtime databases, or live permission controls.

## PnL Paths Reviewed

Reviewed runtime and accounting paths:

- `dashboard/runtime/runtime_smoke_test.py`
- `dashboard/runtime/demo_runtime_runner.py`
- `dashboard/runtime/state_builders/position_state_builder.py`
- `dashboard/runtime/summary_builders/pnl_summary_builder.py`
- `dashboard/runtime/dashboard_state_factory.py`
- dashboard PnL render contracts and renderers
- dashboard/API PnL payload adapters and frontend contract projections
- canonical PnL adapter tests
- runtime, portfolio, paper lifecycle, options lifecycle, and RC1 validation tests

## Diagnostic Evidence

Smoke fixture positions:

| Symbol | Side | Qty | Entry | Mark | Asset | Realized | Unrealized |
| --- | --- | ---: | ---: | ---: | --- | ---: | ---: |
| `BTC-USD` | `LONG` | `0.05` | `65000.00` | `65500.00` | `CRYPTO` | `0.00` | `25.00` |
| `EUR_USD` | `SHORT` | `1000` | `1.0900` | `1.0875` | `FX` | `0.00` | `2.50` |

Deterministic trace before remediation:

- Position-state total unrealized PnL: `27.50`
- Position-state total realized PnL: `0.00`
- Position-state net PnL: `27.50`
- Asset unrealized PnL: `{"CRYPTO": 25.00, "FX": 2.50}`
- Summary unrealized PnL: `0.00`
- Summary realized PnL: `0.00`
- Summary net PnL: `27.50`
- Expected unrealized PnL: `27.50`
- Actual unrealized PnL: `0.00`
- Difference: `27.50`
- Tolerance: exact smoke assertion

## Root Cause

The defect was a dashboard runtime field-contract mismatch.

`PositionStateBuilder` emits normalized runtime totals as:

- `total_realized_pnl`
- `total_unrealized_pnl`
- `net_pnl`

`PnLSummaryBuilder` consumed only canonical adapter keys:

- `realized_pnl`
- `unrealized_pnl`
- `net_pnl`

As a result, the summary builder accepted `net_pnl=27.50` while defaulting missing `unrealized_pnl` to `0.00`. This created an internally inconsistent dashboard PnL snapshot and triggered the smoke-test fail-closed assertion.

## Root-Cause Categories Evaluated

- Double counting: not present.
- Missing position: not present.
- Closed position included as active: not present in smoke fixture.
- Active position omitted: not present.
- Long/short sign inversion: not present; per-position fixture PnL is already normalized.
- Quantity mismatch: not present.
- Option multiplier mismatch: not applicable to smoke fixture; covered by options regressions.
- Mark versus last-price inconsistency: not present.
- Currency-conversion mismatch: not present; smoke fixture is presentation-normalized.
- Realized PnL included in unrealized PnL: not present.
- Fees included inconsistently: not present.
- Stale snapshot race: not present; fixture is deterministic.
- Different snapshot timestamps: not present; fixture is in-memory.
- Decimal versus float drift: not causal; difference was `27.50`.
- Premature rounding: not causal.
- Incorrect smoke-test expected fixture: not present.
- Repository duplication: not causal.
- Dashboard summary transformation error: present.
- Portfolio equity reconciliation error: adjacent presentation issue; account equity now falls back to account payload when canonical equity is absent.
- Asset-class-specific valuation mismatch: not present.

## Remediation

`PnLSummaryBuilder` now preserves canonical adapter precedence while accepting normalized runtime position-state aliases:

- `realized_pnl` first, then `total_realized_pnl`
- `unrealized_pnl` first, then `total_unrealized_pnl`
- `open_positions` first, then `open_count`
- `closed_positions` first, then `closed_count`
- position-state `equity` first, then account-state `equity`, `total_equity`, or `account_equity`

This keeps canonical PnL authoritative when present and restores consistency for the runtime position-state path used by the smoke harness and demo runner.

## New Regression Coverage

Added `tests/dashboard/test_runtime_pnl_reconciliation.py` covering:

- deterministic smoke fixture per-position PnL evidence
- long and short smoke positions
- portfolio unrealized PnL aggregation
- realized versus unrealized separation
- canonical PnL field precedence over normalized total aliases
- dashboard factory snapshot consistency
- regression for the exact RC1-OPS smoke failure

## Validation Results

- Focused PnL suite: `22 passed`
- Compile check: `PASS`
- `dashboard.runtime.runtime_smoke_test`: `PASSED`
- `dashboard.runtime.demo_runtime_runner`: top-level unrealized PnL now reports `27.50`
- RC1 validation group: `44 passed`
- Phase 164 / Phase 163B.3A / OI-010 / EI-001 group: `45 passed`
- Dashboard/mobile/API group: `27 passed`
- Runtime/operational group: `23 passed`
- Paper/execution safety group: `76 passed`
- Portfolio/options lifecycle group: `137 passed`

## Safety Posture

Required posture remains unchanged:

- `paper_only=true`
- `advisory_only=true`
- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`

No orders were submitted or cancelled. No live execution path was changed or enabled.

## Remediation Verdict

`REMEDIATED_READY_FOR_RC1_OPS_RERUN`

This remediation clears the targeted smoke-test PnL blocker. A clean RC1-OPS rerun is still required before any controlled operational runtime release verdict is issued.
