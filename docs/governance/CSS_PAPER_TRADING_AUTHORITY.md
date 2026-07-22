# CSS Paper Trading Authority

**Programme:** Release Gate 2 — Batch B (AR-006 / AR-007)  
**Status:** ACTIVE  
**Date:** 2026-07-21

## Singular paper authority

| Role | Component | Authority |
| --- | --- | --- |
| Canonical paper execution path | `backend.execution.canonical_execution_integration.CanonicalExecutionIntegration` | Authoritative orchestration entry for paper-gated decisions |
| Validation foundation | `backend.execution.unified_execution_pipeline.UnifiedExecutionPipeline` | Validates/normalizes requests only; returns `validated_not_executed`; **no broker dispatch** |
| Advisory scanner shell | `backend.engine.css_trading_engine.CSSTradingEngine` | **Non-authoritative** (`AUTHORITATIVE_PAPER_ENGINE = False`); scan/score/filter only |

## Honesty rules

1. Validation success is not order acceptance or fill.
2. Scanner shells must not be described as the trading engine of record.
3. Live mode remains rejected by the unified validation pipeline.
4. Broker dispatch + journal remain future work; they are not implied by this authority designation.
