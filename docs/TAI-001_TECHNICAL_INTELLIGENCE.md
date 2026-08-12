# TAI-001 Technical / Price-Action Intelligence

## Scope

TAI-001 adds a deterministic, advisory-only technical intelligence layer in `backend.intelligence.technical_intelligence`. It consumes caller-supplied OHLCV candles and returns typed machine-readable evidence. It does not fetch market data, access brokers, place orders, reserve exposure, alter credentials, or grant execution authority.

## Canonical Integration

- Market data seam: existing opportunity candidates carry `market_snapshot.candles` and optional `market_snapshot.timeframes`.
- Intelligence seam: `backend.trading.autonomous_opportunity_intelligence_engine.AutonomousOpportunityIntelligenceEngine` now calls `TechnicalIntelligenceEngine` and stores its output under `technical_intelligence`.
- Ranking seam: technical evidence contributes only 8% of `ranking_v2.weighted_score` through `abs(directional_score) * confidence`; it does not change Unified Trade Gate approval.
- Outcome attribution seam: the full technical snapshot includes raw indicator observations, normalized component contributions, configuration schema version, timestamp, instrument, timeframe, confidence, patterns, and multi-timeframe agreement.

## Output Contract

`TechnicalIntelligenceSnapshot` includes:

- `schema_version`, `instrument`, `timeframe`, `timestamp`, `freshness`, `sample_count`;
- data quality fields: `data_quality`, `insufficient_data`, `data_warnings`;
- trend, momentum, volatility, volume, support/resistance, breakout, and candlestick observations;
- `directional_score` normalized to `[-1.0, 1.0]`;
- `confidence` normalized to `[0.0, 1.0]`, distinct from direction;
- `component_contributions` with per-component score, confidence, weight, weighted score, and reasons;
- `advisory_only=True`, `execution_allowed=False`, `live_trading_blocked=True`.

`MultiTimeframeTechnicalIntelligence` wraps per-timeframe snapshots and reports agreement, dominant direction, higher-timeframe confirmation, conflict indicators, and confidence.

## Indicators And Scoring

- SMA: arithmetic average over the configured trailing window.
- EMA: seeded with the first full-window SMA, then updated with `alpha = 2 / (window + 1)`.
- RSI: trailing average gains/losses over the configured period.
- MACD: EMA fast minus EMA slow, plus EMA signal and histogram.
- ATR: trailing average true range using current high/low and previous close.
- Bollinger Bands: trailing SMA plus/minus configured standard-deviation multiplier.
- Normalized volatility: trailing standard deviation of close-to-close returns.
- Support/resistance: prior candles only, excluding the current candle.
- Breakout/breakdown: current close versus prior support/resistance, with optional volume confirmation.
- Candlestick observations: doji, hammer, shooting star, bullish engulfing, bearish engulfing. These are descriptive evidence only and carry no predictive score.

Composite score uses configurable normalized weights across trend, momentum, volatility, volume, structure, and patterns. Missing components receive zero confidence and do not silently become high-confidence neutral evidence.

## Data Quality And Anti-Lookahead Rules

The engine fails closed for malformed OHLC, duplicate timestamps, negative volume, non-finite values, missing candles, insufficient history, stale data, and out-of-order timestamps. Out-of-order rows are sorted but marked degraded.

At time T, calculations use only rows up to T. Rolling windows are trailing, never centered. Support and resistance exclude the current candle, so a future high/low cannot become historically known. The module does not forward-fill values from future observations.

## Safety Boundary

The module imports only standard-library utilities and typing/dataclass support. It does not import broker, order, credential, live runtime, exposure reservation, or execution gateway modules. Existing governance remains authoritative:

- Unified Trade Gate and opportunity ranking still determine whether an advisory opportunity is blocked or ranked.
- Execution gateways, Margin Gate, RBAC, Capital Governor, AntiBleedGuard, kill switches, and emergency stops are unchanged.
- All TAI payloads explicitly report `execution_allowed=False`.

## Limitations

TAI-001 does not claim profitability, optimize weights, infer missing implied volatility, or fabricate missing timeframes. It uses realized OHLCV evidence only.
