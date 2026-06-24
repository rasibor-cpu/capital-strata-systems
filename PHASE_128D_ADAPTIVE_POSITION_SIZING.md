# Phase 128D Adaptive Position Sizing

## Summary

Phase 128D adds a backend-only adaptive position sizing engine that converts approved capital allocation rows into sized recommendations without altering execution behavior.

## Scope

- Validate sizing inputs fail-closed.
- Respect capital limits, risk budgets, and confidence.
- Return per-symbol sizing rows with recommended capital and sizing status.
