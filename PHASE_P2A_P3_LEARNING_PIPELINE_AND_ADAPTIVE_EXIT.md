# PHASE P2A + P3: Learning Pipeline Integration and Adaptive Exit Engine

## Summary
This phase connects completed trade closes into canonical learning repositories and adds a recommendation-only adaptive exit engine.

## Added modules
- backend/analytics/learning_pipeline_integration.py
- backend/analytics/adaptive_exit_engine.py

## P2A learning pipeline behavior
When a completed trade payload is submitted, the integration writes to:
1. TradeOutcomeRepository
2. TradeContextRecorder
3. RegimeHistoryRepository
4. StrategyMemoryRepository

### Guarantees
- Fail closed on invalid completed trade payload.
- Duplicate trade IDs fail closed and do not silently duplicate memory.
- Missing or unsupported regime values are normalized to `UNKNOWN`.
- Strategy memory records include `realized_pnl` and computed `win` flag.
- No broker calls and no execution behavior changes.

## P3 adaptive exit engine behavior
Inputs:
- open trade context
- market regime
- strategy memory summary
- current unrealized PnL
- holding duration
- volatility
- trend strength

Outputs:
- trade_id
- symbol
- action
- exit_reason
- confidence
- recommended_stop
- recommended_take_profit
- recommended_trailing_stop
- max_hold_seconds

Supported actions:
- HOLD
- TAKE_PROFIT
- STOP_LOSS
- TRAIL
- TIME_EXIT
- REDUCE

### Guarantees
- Fail closed on invalid input.
- Recommendation-only behavior (no execution side effects).
- Deterministic output for identical inputs.

## Tests added
- tests/test_learning_pipeline_integration.py
- tests/test_adaptive_exit_engine.py
