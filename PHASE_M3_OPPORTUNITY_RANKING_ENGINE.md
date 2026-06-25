# PHASE M3 - Opportunity Ranking Engine and Trade Tab Recommendations

## Summary

Phase M3 adds a deterministic opportunity ranking layer on top of the canonical instrument universe and intelligence pipeline outputs.

The Trade tab now answers:

- What should I consider trading right now?

while preserving safety constraints:

- no auto-execution
- no RBAC bypass
- no risk-gate bypass
- no live permission changes

## Components

## 1. Ranking Engine

File:
- backend/trading/opportunity_ranking_engine.py

Exposes:
- OpportunityRankingEngine
- OpportunityRankingEngineError
- RankedOpportunity

Each RankedOpportunity includes:
- rank
- symbol
- display_name
- asset_class
- broker
- action
- confidence
- opportunity_score
- market_regime
- selected_strategy
- signal_strength
- expected_reward
- expected_risk
- risk_score
- allocation
- position_size
- portfolio_risk
- tradable
- paper_supported
- live_supported
- status
- reason
- diagnostics
- last_updated

## 2. Scoring Model

Deterministic score bounded to 0-100.

Weighted factors:
- confidence (positive)
- signal_strength (positive)
- expected_reward ratio (positive)
- expected_risk ratio (negative)
- portfolio_risk (negative)
- concentration_score (negative)
- strategy_score (positive)
- market_regime multiplier (penalizes UNKNOWN)
- tradability and paper support bonuses/penalties

Additional rules:
- blocked actions receive explicit score penalty
- unknown regime applies reduction multiplier
- non-tradable instruments are penalized

## 3. Ranking Inputs

Inputs are derived from existing components:
- InstrumentUniverse for candidate symbols and support flags
- IntelligenceOrchestrator for decision, confidence, regime, allocation, sizing, reward/risk
- CSSUnifiedTradeGate for governance approval context in action resolution

No duplicate decision pipeline was introduced.

## 4. Trade Tab Behavior

Trade tab now displays ranked opportunities table above the ticket.

Visible columns:
- Rank
- Symbol
- Asset Class
- Broker
- Action
- Score
- Confidence
- Regime
- Strategy
- Risk
- Paper Support
- Status

Selection behavior:
- clicking Use populates trade symbol and asset class fields only
- no POST, no broker call, no execution side effects
- user must still submit explicitly

## 5. Feed / API Integration

Launcher/mobile endpoints:
- GET /mobile/opportunities
- GET /mobile/opportunities/top
- GET /mobile/opportunities/asset-class/{asset_class}

Fail-closed behavior:
- ranking errors return empty feeds

## 6. Alerts

Warning-level canonical alerts with dedupe keys are emitted for:
- no tradable opportunities
- all top opportunities blocked
- low confidence opportunities
- stale ranking feed sample

Alert emission uses existing AlertRepository and does not spam due to dedupe keys.

## 7. Safety Constraints

Explicitly preserved:
- mobile selection does not execute trades
- trade submission remains paper-only validation path
- existing risk and governance gates remain active for any executable path

## Known Limitations

- Candidate market snapshots are deterministic synthetic snapshots for ranking continuity, not live market microstructure.
- Strategy context defaults are heuristic when deep strategy-memory context is absent.
- Staleness check currently evaluates top sample timestamps only.

## Next Recommended Enhancements

1. Replace synthetic candidate market snapshots with a cached real-market signal adapter while preserving fail-closed behavior.
2. Add per-user ranking personalization with RBAC-safe strategy exposure constraints.
3. Add explicit regime-aware per-asset weighting configuration in external config.
