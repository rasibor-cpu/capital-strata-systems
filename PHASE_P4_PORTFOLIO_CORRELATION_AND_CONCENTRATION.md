# PHASE P4: Portfolio Correlation and Concentration Guard

## Summary
This phase introduces a backend-only portfolio correlation engine and a concentration guard recommendation layer.

## Added modules
- backend/analytics/portfolio_correlation_engine.py
- backend/analytics/concentration_guard.py

## PortfolioCorrelationEngine capabilities
- correlation groups
- asset-class exposure
- symbol exposure
- long exposure
- short exposure
- directional exposure
- portfolio concentration score

## Correlation groups supported
- BTC / ETH / SOL
- major USD FX
- equity index futures
- configurable groups

## ConcentrationGuard capabilities
- single symbol concentration
- asset-class concentration
- correlated exposure
- directional concentration

## Recommendations
- ALLOW
- REDUCE_SIZE
- BLOCK

## Behavior guarantees
- Deterministic output
- Fail closed on invalid inputs
- Recommendation-only, with no execution side effects
- Configurable thresholds

## Tests added
- tests/test_portfolio_correlation_engine.py
- tests/test_concentration_guard.py
