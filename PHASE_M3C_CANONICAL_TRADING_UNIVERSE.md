# CSS M3C - Canonical Trading Universe Decision Console

## Scope
Transforms Trade tab into a canonical decision console driven by a curated universe and read-only intelligence outputs.

## Delivered
- Added canonical registry:
  - `backend/trading/canonical_trading_universe.py`
- Added canonical universe APIs:
  - `GET /mobile/trading-universe`
  - `GET /mobile/trading-universe/grouped`
  - `GET /mobile/opportunity-summary/{symbol}`
  - `GET /mobile/top-opportunities`
- Trade tab now includes:
  - grouped selector with `optgroup`
  - top opportunities card (Top 10, Green/Amber/Red)
  - instant search filter
  - favorites toggle with local persistence (`localStorage`)
  - mode visibility badge (PAPER MODE / LIVE MODE)
  - fail-closed unavailable instruments rendered disabled with reason
  - read-only decision panel populated on selection
- Opportunity integration surfaced in summary payload:
  - OpportunityRankingEngine
  - IntelligenceOrchestrator
  - PortfolioCorrelationEngine
  - ConcentrationGuard
  - StrategyIntelligenceEngine
  - MarketRegimeEngine
  - AdaptiveExitEngine

## Safety
- Selecting instruments/opportunities only populates selector and decision panel.
- No automatic trade execution.
- Existing paper-only trade request endpoint remains unchanged and gated.
- RBAC/risk gate/live controls are not bypassed.
