# PHASE P1: Market Regime Intelligence Foundation

## Summary
This phase introduces canonical market-regime analytics building blocks for backend intelligence and trade-context capture.

## Added modules
- backend/analytics/market_regime_engine.py
- backend/analytics/regime_history_repository.py
- backend/analytics/trade_context_recorder.py

## Canonical regimes
- TRENDING
- RANGING
- BREAKOUT
- REVERSAL
- HIGH_VOLATILITY
- LOW_VOLATILITY
- UNKNOWN

## Market features exposed
- ATR
- volatility
- trend strength
- momentum
- volume state
- price acceleration
- direction
- confidence

## Trade context support
Completed trade context can be normalized with:
- trade_id
- symbol
- asset_class
- strategy
- entry_time
- exit_time
- market_regime
- volatility
- trend_strength
- confidence
- broker
- session

## Regime history support
Persisted regime history includes:
- timestamp
- regime
- symbol
- confidence

Query support:
- recent regimes
- regime counts
- symbol regime history

## Safety behavior
- Repository operations fail closed on invalid/corrupt storage.
- This phase is backend-only and does not alter broker execution, live permissions, RBAC, mobile UI, launcher UI, or trading logic.
