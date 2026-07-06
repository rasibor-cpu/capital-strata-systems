# Phase 156D - Canonical Drawdown Display Consolidation

## Scope

Consolidate runtime drawdown display onto canonical capital-state evaluation so unavailable-capital scenarios no longer show misleading numeric drawdown values.

## Problem Addressed

Legacy tracker output could still print a numeric drawdown (for example 100.0000%) even when capital state was unavailable and drawdown was not computable.

## Consolidation Rules

- Runtime drawdown display must use canonical evaluation from `backend.runtime.capital_state`.
- When `drawdown_status=NOT_COMPUTABLE`, runtime must display:
  - `DRAWDOWN: NOT COMPUTABLE`
  - `DRAWDOWN REASON: <canonical reason>`
  - `CAPITAL STATE: <canonical state>`
- Numeric drawdown display is allowed only when drawdown status is computed.

## Safety Constraints Preserved

- No safety gate weakening.
- No live execution enablement.
- Capital-unavailable and unknown states remain fail-closed.

## Validation

- Added tests for missing credentials, broker-balance unavailable, simulated drawdown display, real funded drawdown display, and canonical field usage in display payload.
