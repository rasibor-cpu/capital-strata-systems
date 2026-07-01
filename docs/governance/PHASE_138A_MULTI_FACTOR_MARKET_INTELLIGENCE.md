# Phase 138A Multi-Factor Market Intelligence

Phase 138A adds advisory-only market intelligence inputs for technical, fundamental, sentiment, and quantitative analysis.
The layer improves explanation quality and validation context without changing execution authority.

## Advisory-Only Design

All engines return `advisory_only: true` and `execution_allowed: false`.
Outputs are inputs to explanation and confidence context only.
They do not approve orders, bypass risk gates, alter broker behavior, enable live trading, or weaken governance.

## Data Sources

The framework uses internal CSS data only:

- runtime portfolio state
- internal price/return/trade history when available
- internal alerts
- recommendation history
- market regime labels
- existing metadata embedded in artifacts

It does not scrape the web, call news APIs, call social APIs, or fetch external fundamentals.

## Engines

- `TechnicalAnalysisEngine`: moving averages, momentum, volatility regime, RSI-like score, breakout/consolidation, technical score.
- `FundamentalAnalysisEngine`: generic internal-metadata quality, valuation status, macro sensitivity, balance quality.
- `SentimentIntelligenceEngine`: internal alert/recommendation/runtime warning sentiment.
- `QuantitativeAlphaEngine`: expectancy, risk-adjusted momentum, drawdown penalty, regime fit.
- `MultiFactorSignalSynthesizer`: combines all components with market regime and portfolio decision context.

## Fail-Closed Behavior

Missing or insufficient data returns `DATA UNAVAILABLE` or `PARTIAL`.
Missing components reduce multi-factor confidence.
Conflicting positive and negative components reduce confidence.

## API And Dashboard

Read-only APIs:

- `/api/technical-analysis`
- `/api/fundamental-analysis`
- `/api/sentiment-intelligence`
- `/api/quantitative-alpha`
- `/api/multi-factor-signal`

The mobile dashboard shows a Market Intelligence section with component signals, multi-factor score, confidence, and reasons.

