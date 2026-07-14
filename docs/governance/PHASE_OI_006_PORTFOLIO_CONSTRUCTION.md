# Phase OI-006 - Options Income Portfolio Construction

Date: 2026-07-14

Branch: `css-unified-consolidation-2026-07-13`

## Purpose

Phase OI-006 adds a paper-only Options Income Portfolio Construction Engine. It consumes OI-003 accepted opportunities and OI-005 managed OI-004 paper positions to construct advisory options income portfolios.

This phase never creates orders, submits orders, cancels orders, routes execution, calls broker APIs, changes permissions, modifies live runtime state, or enables live trading.

## Architecture

The implementation is split into paper-only modules:

- `backend/options/options_income_portfolio.py` builds the canonical portfolio payload.
- `backend/options/options_income_allocator.py` allocates paper capital across accepted opportunities and existing paper positions.
- `backend/options/options_income_constraints.py` enforces fail-closed concentration and capital constraints.
- `backend/options/options_income_diversification.py` calculates underlying, expiry, strategy, sector, and assignment diversification.
- `backend/options/options_income_laddering.py` evaluates weekly, monthly, and mixed expiry ladders.
- `backend/options/options_income_targets.py` calculates premium targets, yield, premium consistency, and capital efficiency.
- `backend/options/options_income_rebalancer.py` generates advisory portfolio rebalance recommendations.

## Portfolio Construction

OI-006 supports deterministic paper portfolios across:

- covered calls
- cash-secured puts
- multiple underlyings
- multiple expiries
- capital buckets
- income targets

Portfolio construction produces structured advisory payloads only.

## Capital Allocation

The allocator tracks:

- allocated capital
- available capital
- reserved collateral
- utilized collateral
- unused collateral
- portfolio utilization

Existing OI-004 paper positions are treated as reserved collateral. OI-003 accepted opportunities are considered for additional paper allocation only when constraints allow.

## Diversification

The constraint and diversification engines evaluate:

- single-underlying concentration
- single-expiry concentration
- single-strategy concentration
- sector concentration
- capital concentration
- assignment concentration
- expiry concentration

Violations are rejected or recorded as blockers in the advisory allocation plan.

## Expiry Laddering

The ladder builder supports:

- weekly ladders
- monthly ladders
- mixed ladders
- ladder quality score
- expiry distribution

Malformed expiries fail closed.

## Income Targets

The target calculator reports:

- monthly premium target
- annual premium target
- portfolio yield
- yield on collateral
- expected premium
- premium consistency
- capital efficiency

## Rebalancing

The rebalancer emits advisory recommendations only:

- Increase Allocation
- Reduce Allocation
- Replace Opportunity
- Roll Portfolio
- Maintain Portfolio

These recommendations are not orders and cannot authorize execution.

## Safety Guarantees

OI-006 preserves:

- `advisory_only=true`
- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`

The implementation does not import broker adapters, execution routing, runtime servers, Desktop runtime, credentials, tokens, authentication, `.env`, PEM files, runtime databases, live execution modules, or permission controls.

## Fail-Closed Behavior

OI-006 rejects or blocks:

- negative capital
- duplicate positions
- duplicate allocations
- invalid ladders
- concentration violations
- unsupported strategies
- invalid collateral
- invalid portfolio state
- repository corruption
- unsafe advisory flags

## Relationship To Prior Phases

OI-002 defines covered-call and cash-secured-put strategy summaries.

OI-003 provides accepted income opportunities.

OI-004 creates paper income lifecycle positions.

OI-005 manages paper positions, health, metrics, and rolling advisory.

OI-006 constructs paper portfolios from those canonical inputs.

## Out Of Scope

This phase does not implement broker integration, live execution, dashboard activation, institutional deployment, or production certification.
