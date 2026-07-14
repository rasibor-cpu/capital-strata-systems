# Phase OI-005 - Options Position Management And Rolling Engine

Date: 2026-07-14

Branch: `css-unified-consolidation-2026-07-13`

## Purpose

Phase OI-005 adds canonical paper-only position management, position health, income metrics, and rolling recommendations for existing OI-004 paper income positions.

The phase operates only on paper positions already created by the OI-004 lifecycle engine. It does not create broker orders, submit roll orders, cancel orders, route execution, call external APIs, modify live runtime state, or authorize trading.

## Architecture

The implementation extends the Options Income Engine with these paper-only modules:

- `backend/options/options_position_manager.py` exposes additive paper-income management helpers while preserving existing long-option position behavior.
- `backend/options/position_health.py` calculates deterministic health and roll eligibility.
- `backend/options/income_position_metrics.py` calculates lifetime premium, yield, duration, rolling history, assignment history, premium capture, and capital efficiency.
- `backend/options/rolling_candidates.py` generates deterministic advisory roll candidates.
- `backend/options/roll_decision_engine.py` selects a single advisory recommendation from candidate rolls.
- `backend/options/rolling_engine.py` coordinates repository-backed paper roll evaluation.

## Position Management

OI-005 manages existing OI-004 paper positions in active, expiring, completed, assigned, exercised, expired-worthless, and closed-early states. It can list, inspect, score, calculate metrics, and record advisory roll recommendation history.

It does not alter execution authority and does not transition positions into live or broker-backed states.

## Position Health

Position health includes:

- days remaining
- premium retained
- premium decay
- collateral utilization
- yield remaining
- assignment exposure
- early close eligibility
- roll eligibility
- health score

Health outputs are advisory only and carry the standard safety flags.

## Rolling Recommendations

The rolling engine evaluates deterministic advisory outcomes:

- Roll Forward
- Roll Up
- Roll Down
- Roll Out
- No Roll

Every recommendation includes reason, expected premium, capital impact, yield impact, risk impact, confidence, and advisory-only safety flags.

No recommendation is an order ticket. No recommendation can route execution.

## Metrics

Income position metrics track:

- lifetime premium
- annualized yield
- yield per collateral
- position duration
- rolling history
- assignment history
- premium capture percentage
- capital efficiency

## Safety Guarantees

OI-005 preserves:

- `advisory_only=true`
- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`

The implementation does not import broker adapters, execution routing, credentials, authentication, runtime server components, live controls, `.env`, PEM material, or runtime databases.

## Fail-Closed Behavior

OI-005 rejects:

- missing positions
- completed positions for rolling
- duplicate paper identifiers through the OI-004 repository
- invalid states
- negative collateral
- negative premium
- invalid expiry or timestamps
- malformed strategy data
- unsupported strategies
- repository corruption
- unsafe advisory flags

## Relationship To Prior Phases

OI-002 defines the covered-call and cash-secured-put strategy summaries.

OI-003 scans and ranks paper-safe income candidates.

OI-004 creates and maintains paper lifecycle positions.

OI-005 consumes only those OI-004 paper positions and adds management, health, metrics, and advisory rolling recommendations.

## Out Of Scope

This phase does not implement:

- live options brokerage
- live order routing
- roll order submission
- assignment execution
- exercise instructions
- dashboard activation
- portfolio deployment
- production certification
