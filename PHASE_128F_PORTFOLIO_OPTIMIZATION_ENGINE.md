# Phase 128F Portfolio Optimization Engine

## Summary

Phase 128F adds a backend-only portfolio optimization engine that interprets allocation, sizing, and strategy recommendation outputs to produce portfolio-level recommendations without touching execution paths.

## Scope

- Validate asset class and exposure limits fail-closed.
- Respect max symbol and total allocation constraints.
- Reduce or block symbols when strategy promotion recommends demotion or disable.
- Return portfolio statuses of APPROVED, REDUCED, RESTRICTED, or BLOCKED.
