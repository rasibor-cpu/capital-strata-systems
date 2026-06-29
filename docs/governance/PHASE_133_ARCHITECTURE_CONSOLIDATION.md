# Phase 133 Architecture Consolidation

## Purpose

Phase 133 remediates high-value architecture audit findings from Phases 130-132. It is corrective and consolidating only. It does not add trading features or execution authority.

## Regime Enum Alignment

Phase 133 introduces canonical portfolio regime constants in `backend/portfolio/constants.py`:

- `TRENDING_UP`
- `TRENDING_DOWN`
- `RANGING`
- `HIGH_VOLATILITY`
- `LOW_VOLATILITY`
- `CORRELATION_STRESS`
- `UNKNOWN`

`MarketRegimeIntelligence` and `RegimeAwareAllocationEngine` now use the same canonical regime names. Defensive handling is enforced for:

- `TRENDING_DOWN`
- `CORRELATION_STRESS`
- `HIGH_VOLATILITY`
- `UNKNOWN`

`TRENDING_UP` can support selective risk-on allocation only when downside metrics are acceptable.

## GET/POST Persistence Separation

`GET /api/portfolio-decision` is now read-only and idempotent. It generates the current advisory package but does not append to decision package persistence.

Explicit persistence is available through:

- `POST /api/portfolio-decision/record`

The POST route records one advisory package under `artifacts/portfolio/` and remains advisory-only.

## Request-Scoped Memoization

Mobile dashboard context generation now computes the full portfolio decision input bundle once and threads that shared object through:

- portfolio decision
- validation
- advisory consistency
- explainability
- dependent dashboard cards

This avoids redundant recomputation and prevents accidental persistence side effects.

## Shared Constants And Utilities

Phase 133 adds:

- `backend/portfolio/constants.py`
- `backend/portfolio/utils.py`

Shared utilities include safe float parsing, bounded values, safe numeric series parsing, allocation normalization, and advisory response helpers. Extraction was conservative to reduce remediation risk.

## Advisory-Only Safety Preservation

No broker execution behavior was changed. No live trading was enabled. No Runtime Supervisor, Unified Trade Gate, Capital Governor, RBAC, AntiBleedGuard, Portfolio Risk Committee, or other risk gate behavior was weakened.

Strategy attribution now consistently returns:

- `advisory_only: true`
- `execution_allowed: false`

## Addressed Audit Findings

- Regime enum mismatch between regime intelligence and regime-aware allocation.
- GET endpoint persistence side effect for portfolio decisions.
- Repeated full advisory pipeline computation during dashboard context build.
- Duplicate constants and low-risk utility helpers.
- Strategy attribution advisory-only response consistency.

## Deferred Findings

Broader refactors across all portfolio engines remain deferred. Phase 133 intentionally avoids large rewrites, dependency changes, and execution-path changes.
