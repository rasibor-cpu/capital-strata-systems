# Phase 129D Capital Rotation

## Scope

The Capital Rotation Engine produces deterministic target allocation recommendations from portfolio intelligence and allocation candidates.

## Allocation Rules

- Recommendations are advisory only.
- Allocations are non-negative.
- Allocations are normalized in basis points.
- Final target allocation percentages sum exactly to `100.0`.
- Missing or invalid data fails closed to `{"CASH": 100.0}`.

## Penalties

The rotation score penalizes:

- High drawdown
- Weak Sortino
- Poor capital efficiency
- High concentration
- Excessive correlation

## Dashboard/API Integration

Read-only endpoints:

- `/api/portfolio-intelligence`
- `/api/capital-rotation`

Mobile dashboard behavior:

- Shows portfolio intelligence score, recommendation, drawdown, Sortino, capital efficiency, correlation, and capital rotation targets.
- Shows `DATA UNAVAILABLE` when source evidence is missing.

## Safety

- No broker execution behavior changes
- No live trading enablement
- No risk gate weakening
- No Runtime Supervisor decision changes
- No Capital Governor decision changes
