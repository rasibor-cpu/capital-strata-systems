# Phase OI-007 - Options Risk, Greeks Governance, And Stress Testing

Date: 2026-07-14

Branch: `css-unified-consolidation-2026-07-13`

## Purpose

Phase OI-007 adds a paper-only and advisory-only risk governance layer for the Options Income Engine. It consumes OI-006 paper portfolios, OI-005 managed paper positions, and explicit canonical Greeks/IV inputs to assess options income portfolio risk.

This phase never creates orders, submits orders, cancels orders, routes execution, calls broker APIs, changes permissions, modifies live runtime state, or enables live trading.

## Architecture

The implementation is split into paper-only modules:

- `backend/options/options_greeks_aggregator.py` aggregates position, underlying, strategy, expiry, and portfolio Greeks.
- `backend/options/options_income_risk_budget.py` evaluates configurable immutable risk budgets.
- `backend/options/options_income_risk_limits.py` converts risk budgets into hard and advisory limit outcomes.
- `backend/options/options_income_assignment_risk.py` calculates deterministic assignment exposure.
- `backend/options/options_income_volatility_risk.py` evaluates IV, vega, volatility regime, and short-volatility concentration.
- `backend/options/options_income_stress_testing.py` runs deterministic paper stress scenarios.
- `backend/options/options_income_risk_governance.py` coordinates the canonical advisory risk assessment.

## Greeks Governance

OI-007 aggregates delta, gamma, theta, vega, and rho at:

- position level
- underlying level
- strategy level
- expiry bucket level
- portfolio level

Missing Greeks are marked `UNAVAILABLE`. Malformed Greeks fail closed. Values are never fabricated.

## Risk Budgets And Limits

Risk budgets cover:

- net delta
- absolute delta
- gamma
- theta
- vega
- rho
- underlying concentration
- expiry concentration
- strategy concentration
- assignment exposure
- collateral utilization
- volatility exposure
- stressed loss

Statuses are deterministic: `GREEN`, `AMBER`, `RED`, or `UNAVAILABLE`.

Hard limit breaches reject paper approval. Advisory breaches produce warnings.

## Assignment Risk

Assignment risk tracks:

- contracts exposed
- shares potentially called away
- cash potentially required
- assignment notional
- assignment concentration
- ITM exposure
- near-expiry exposure
- underlying concentration
- expiry concentration
- portfolio assignment ratio

## Volatility Risk

Volatility risk tracks:

- implied-volatility exposure
- vega concentration
- volatility regime
- volatility expansion risk
- volatility contraction risk
- premium adequacy
- short-volatility concentration
- expiry-specific volatility exposure

Missing IV is explicitly reported as unavailable.

## Stress Testing

Stress scenarios are deterministic and include underlying moves, volatility moves, combined scenarios, near-expiry adverse movement, and assignment concentration events. Where repricing data is unavailable, OI-007 uses documented deterministic linear Greeks approximations and marks approximation flags.

No randomness, Monte Carlo, broker calls, or execution instructions are used.

## Governance Assessment

The governance engine returns:

- portfolio risk status
- approval status
- risk score
- limit breaches
- warnings
- unavailable data
- stress summary
- assignment summary
- Greeks summary
- volatility summary
- advisory recommendations

Approval states are:

- `APPROVED_PAPER`
- `APPROVED_WITH_WARNINGS`
- `REJECTED_RISK_LIMIT`
- `REJECTED_INVALID_DATA`

The assessment always preserves `execution_allowed=false`, `live_trading_blocked=true`, and `paper_only=true`.

## Advisory Recommendations

Recommendations are deterministic and advisory-only, including concentration reduction, assignment reduction, collateral reduction, theta improvement, vega reduction, portfolio resizing, rebalancing, insufficient data, and maintain-portfolio guidance.

## Safety Guarantees

OI-007 preserves:

- `advisory_only=true`
- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `paper_only=true`

The implementation does not import broker adapters, execution routing, runtime servers, Desktop runtime, credentials, tokens, authentication, `.env`, PEM files, runtime databases, broker connectivity, live execution modules, or permission controls.

## Fail-Closed Behavior

OI-007 rejects or marks invalid:

- missing portfolios
- duplicate allocations
- unsupported strategies
- negative collateral
- negative capital
- malformed Greeks
- missing Greeks
- missing IV
- invalid IV
- completed positions included as active
- execution-enabled posture
- repository corruption
- risk-limit computation failures
- stress-test computation failures

## Relationship To Prior Phases

OI-002 defines covered-call and cash-secured-put strategy summaries.

OI-003 provides accepted income opportunities.

OI-004 creates paper income lifecycle positions.

OI-005 manages paper positions, health, metrics, and rolling advisory.

OI-006 constructs paper income portfolios.

OI-007 assesses paper risk, Greeks, assignment, volatility, stress scenarios, and governance approval.

## Out Of Scope

This phase does not implement dashboard activation, broker integration, live orders, live routing, assignment execution, institutional deployment, production readiness, or live certification.
