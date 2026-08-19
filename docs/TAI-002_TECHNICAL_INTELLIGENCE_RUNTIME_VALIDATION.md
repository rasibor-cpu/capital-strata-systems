# TAI-002 Technical Intelligence Runtime / Integration Validation

**Task:** TAI-002  
**Baseline:** `css-v1.0.1-maintenance` @ `ba3ff07478164fb1f5011fbc6f5d44955fb3f42d`  
**Branch:** `css-tai-002-runtime-validation-r2`  
**Supersedes:** `css-tai-002-runtime-validation` / PR #54  

## Purpose

TAI-002 validates the already-merged TAI-001 technical intelligence engine through the canonical CSS intelligence and opportunity-ranking seam. It does not add a second trading architecture and does not grant execution authority.

## Integration seam

1. Caller-supplied OHLCV candles (`market_snapshot.candles` / `market_snapshot.timeframes`)
2. `TechnicalIntelligenceEngine.analyze_timeframes`
3. `AutonomousOpportunityIntelligenceEngine.analyze` stores the payload under `technical_intelligence` and contributes 8% of `ranking_v2.weighted_score` as `abs(directional_score) * confidence`
4. `OpportunityRankingEngine` exposes that payload at `diagnostics.intelligence.technical_intelligence`
5. Mission Control `build_opportunity_ranking` projects a read-only observability contract onto each opportunity row

Unified Trade Gate approval remains independent of TAI. Action resolution still requires both an ALLOW intelligence decision and an approved gate.

## Safety overlay

The autonomous intelligence seam and the ranking consumption seam force:

- `advisory_only=True`
- `execution_allowed=False`
- `live_trading_blocked=True`
- `broker_execution_armed=False`

A forged TAI payload that advertises execution authority is stripped before ranking or Mission Control display.

## Observability contract

Mission Control opportunity rows expose `technical_intelligence` with:

- directional score, confidence, dominant direction
- agreement / conflict indicators / higher-timeframe confirmation
- freshness, data quality, insufficient-data flag, regime
- evidence reasons and component contributions
- hard-coded advisory/execution-disallowed markers
- `execution_authority: NONE`

This reuses the existing Mission Control opportunity-ranking builder. It does not create a second dashboard and cannot arm broker execution.

## Anti-lookahead / fail-closed

At evaluation time T, appending strictly future candles must either leave the current-time technical ranking component unchanged or fail closed to zero directional score, zero confidence, and zero technical ranking weight. Insufficient, malformed, stale, and future-timestamped evidence cannot create a ranking advantage.

## Isolation

TAI-001 source and the autonomous intelligence engine do not import or call Unified Trade Gate, AntiBleedGuard, Capital Governor, kill switches, or broker order APIs. Ranking still consults `CSSUnifiedTradeGate.approve_trade`. A denying gate remains BLOCK even when TAI evidence is maximally bullish.

## Out of scope

MI-EXT, RC-LIVE reconciliation, world-event intelligence, manual-confirmation trading, and autonomous live trading are later tasks.
