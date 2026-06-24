# Phase T1 Canonical Trade Lifecycle

## Summary

This bundle adds a backend-only canonical adapter for normalizing completed trade outcomes across FX, crypto, options, and futures before persisting them into the Phase 128A trade outcome warehouse.

## Scope

- Introduces CanonicalTradeLifecycle and CanonicalTradeLifecycleError
- Normalizes open and close payloads into the canonical trade outcome schema
- Persists completed closes through TradeOutcomeRepository / persist_completed_trade_outcome
- Fails closed on missing required fields, unsupported asset classes, missing timestamps, and duplicate trade IDs

## Notes

- The implementation is backend-only and does not alter broker execution behavior, RBAC, live/paper controls, or UI launchers.
- All persistence is routed through the existing trade outcome repository and repository-level fail-closed behavior.
