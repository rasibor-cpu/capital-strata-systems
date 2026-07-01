# CSS Phase 139A - Adaptive Intelligence & Performance Attribution

Phase 139A adds a read-only learning and attribution layer for advisory market
intelligence. It evaluates historical advisory factor evidence against later outcomes,
then produces explainable recommendations for future advisory weighting review.

## Scope

The framework covers:

- factor performance
- factor attribution
- rolling reliability
- regime learning
- adaptive weight recommendations
- confidence calibration learning
- engine health learning

## Read-Only Boundary

The learning layer reads existing advisory history, completed-trade learning records, and
runtime dashboard context. It does not persist new records from GET endpoints, submit
orders, change broker state, alter portfolio allocation, update risk gates, or grant
execution authority.

Every response preserves:

```python
{
    "advisory_only": True,
    "execution_allowed": False,
}
```

## Methodology

Factor performance compares factor scores with subsequent outcome direction. Factor
attribution combines centered factor scores, regime-aware weights, and realized outcomes
to estimate directional contribution. Rolling reliability tracks recent hit-rate stability.
Regime learning groups factor behavior by market regime. Adaptive weight recommendations
normalize learned evidence into advisory-only factor weights that sum to exactly 100.0.

Confidence calibration learning compares expected confidence with observed advisory hit
rate. Engine health learning reports whether the learning packages are complete enough to
use as advisory evidence.

## Dashboard And APIs

The mobile dashboard adds a `Learning & Optimization` section. Read-only APIs expose:

- `GET /api/factor-performance`
- `GET /api/factor-attribution`
- `GET /api/rolling-reliability`
- `GET /api/regime-learning`
- `GET /api/adaptive-weight-recommendations`
- `GET /api/confidence-calibration-learning`
- `GET /api/engine-health-learning`

Missing or insufficient data returns safe `DATA UNAVAILABLE` or `PARTIAL` packages without
side effects.
