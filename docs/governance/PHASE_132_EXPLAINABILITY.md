# Phase 132 Explainability

## Purpose

Phase 132 adds a dedicated explainability layer for portfolio advisory decisions. It converts engine outputs into human-readable traceability.

## Explanation Pipeline

The explainability engine summarizes:

- adaptive portfolio recommendation
- portfolio intelligence status and score
- risk committee status and concerns
- quantitative metrics
- market regime and risk bias
- active policy profile
- validation violations and warnings
- advisory consistency conflicts

Every recommendation should include a primary explanation and supporting detail.

## Conflict Resolution

When inputs disagree, explanations name the conflicting signal. The advisory consistency checker recommends the most conservative advisory signal when conflicts are present.

## Execution Boundary

Explainability output is informational. It does not approve execution, override governance, change allocation state, or enable autonomous trading.
