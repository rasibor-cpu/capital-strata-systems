# Phase 132 Decision Validation

## Purpose

Phase 132 adds validation for canonical advisory packages. Validation checks whether a recommendation satisfies policy, risk, capital, committee, and supervisor constraints.

## Validation Pipeline

The validation engine checks:

- policy recommendation ceiling
- max drawdown tolerance
- concentration limit
- minimum cash reserve
- red risk committee status
- supervisor status
- missing inputs

The output is:

- `PASS`
- `WARN`
- `FAIL`

Failures force the advisory recommendation to `PAUSE_NEW_TRADES`.

## Conflict Resolution

Validation violations are treated as higher priority than opportunistic recommendations. When validation and recommendation conflict, the conservative validation result wins.

## Execution Authority Separation

Validation is advisory-only. It does not change broker execution behavior, Runtime Supervisor decisions, Unified Trade Gate decisions, Capital Governor behavior, RBAC, AntiBleedGuard, or Portfolio Risk Committee authority.
