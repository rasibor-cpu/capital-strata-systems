# Phase 155AB: Opportunity Intelligence and Capital Scoring Engine

## Purpose

Phase 155AB adds an institutional advisory layer for ranking eligible trading opportunities by expected risk-adjusted profitability and capital efficiency. It helps operators review opportunity quality, expected value, broker/execution conditions, diversification value, and capital use without changing execution behavior.

## Architecture

The implementation is additive and lives under `backend/analytics`.

Core components:

- `ExpectedValueEngine`
- `RiskAdjustedOpportunityScoringEngine`
- `OpportunityIntelligenceEngine`
- `build_opportunity_intelligence_report`

The dashboard runtime exposes the report at:

- `/api/v1/opportunity-intelligence`

The endpoint reads existing `DashboardState.to_dict()` payloads only. It does not call brokers, submit orders, alter runtime state, or mutate trade gates.

## Scoring Methodology

Each eligible opportunity is evaluated across:

- Asset
- Broker
- Strategy
- Regime
- Signal strength
- Confidence
- Execution quality
- Broker performance
- Liquidity
- Volatility
- Expected holding period
- Portfolio diversification benefit
- Current exposure
- Capital efficiency

The unified opportunity score combines:

- Expected value
- Decision confidence
- Broker performance
- Execution quality
- Regime match
- Liquidity
- Diversification
- Capital efficiency
- Historical reliability

Statuses:

- `GREEN`: high-quality paper-review candidate
- `AMBER`: monitor candidate
- `RED`: do not allocate

## Expected Value

The expected-value model incorporates:

- Historical performance
- Confidence calibration
- Execution quality
- Broker intelligence
- Regime intelligence
- Expected reward
- Expected risk
- Downside penalty
- Liquidity adjustment
- Slippage adjustment

The model returns:

- `expected_value`
- `risk_adjusted_return`
- `expected_drawdown`
- `confidence_adjusted_ev`

## Risk Adjustment

Risk adjustment penalizes downside, weak liquidity, poor execution quality, weak broker performance, poor regime alignment, and inefficient capital use. Safety blockers such as live-authority-shaped fields force the advisory recommendation toward `DO_NOT_ALLOCATE`.

## Opportunity Ranking

The leaderboard sorts eligible opportunities by highest score first. It returns rank, asset, strategy, broker, score, expected value, confidence, capital efficiency, status, and summary.

## Safety Protections

Phase 155AB does not bypass or replace:

- R7 trade gate
- Broker startup gate
- Runtime Supervisor
- Capital Governor
- RBAC
- NO-GO protections
- Live-readiness controls
- Broker execution firewalls

The report always returns:

- `advisory_only: true`
- `execution_allowed: false`
- `live_trading_enabled: false`

## Why Advisory Only

Opportunity intelligence is a decision-support artifact. It can rank candidates and explain their risk-adjusted quality, but it cannot authorize a trade, allocate real capital, arm live execution, or override any existing CSS governance system. All live trading authority remains outside this phase and must continue to pass existing controls.
