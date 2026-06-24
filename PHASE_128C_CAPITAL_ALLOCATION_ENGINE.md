# Phase 128C Capital Allocation Engine

## Summary

Phase 128C introduces a backend-only capital allocation engine that converts profitability rankings into per-symbol allocation recommendations without touching execution or UI controls.

## Scope

- Add a fail-closed capital allocation engine for backend analytics.
- Produce per-symbol allocation rows with symbol, score, trade_count, realized_pnl, allocation_weight, allocation_amount, and status.
- Respect total weight and per-symbol weight caps.
- Restrict symbols that fail minimum-trade or score thresholds.

## Notes

- The engine is read-only from the perspective of broker execution and runtime controls.
- Invalid capital or weight inputs fail closed with explicit exceptions.
