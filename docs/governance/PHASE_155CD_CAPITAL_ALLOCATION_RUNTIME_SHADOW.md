# Phase 155CD: Capital Allocation Runtime Shadow Integration

## Architecture

Phase 155CD completes the Capital Allocation Intelligence Engine as an advisory analytics layer. The new `backend.analytics.capital_allocation_optimizer` module consumes Phase 155AB opportunity intelligence and produces a shadow capital allocation plan.

Runtime order remains:

1. Signal
2. Trade Validation
3. Broker Validation
4. Runtime Supervisor
5. Decision Confidence
6. Opportunity Intelligence
7. Capital Allocation Intelligence
8. Advisory output only

The runtime API exposes the report at `/api/v1/capital-allocation-intelligence`. The frontend contract also exposes a read-only `capital_allocation_intelligence` section for dashboard rendering.

## Allocation Algorithm

The optimizer reviews already-ranked opportunities in leaderboard order. For each opportunity it calculates a proposed shadow allocation using:

- Opportunity rank and score
- Expected value
- Confidence
- Capital efficiency
- Available capital
- Cash reserve policy
- Maximum single-position policy

The optimizer is greedy and deterministic. An opportunity receives shadow capital only if the proposed allocation satisfies all configured portfolio constraints.

## Portfolio Governance

The optimizer respects:

- Maximum portfolio exposure
- Asset-class allocation limits
- Sector allocation limits
- Broker allocation limits
- Strategy allocation limits
- Maximum single-position allocation
- Cash reserve policy
- Existing portfolio exposure where available

If a constraint blocks allocation, the recommendation explains why the opportunity received no capital.

## Capital Efficiency Analysis

The report includes:

- `capital_efficiency_score`
- `expected_portfolio_return`
- `expected_portfolio_risk`
- `expected_drawdown`
- `portfolio_confidence`
- `risk_adjusted_capital_score`
- `diversification_score`
- `cash_allocation`

These metrics support portfolio review only. They are not trade authorization signals.

## Runtime Integration

The integration is read-only. It consumes `DashboardState.to_dict()` snapshots and Phase 155AB opportunity intelligence. It does not call brokers, does not write orders, does not alter runtime supervision, and does not mutate existing trade decisions.

## Safety Controls

Phase 155CD does not bypass or weaken:

- R7 Trade Gate
- Runtime Supervisor
- Broker Startup Gates
- Capital Governor
- Broker Readiness
- RBAC
- Live Mode protections
- NO-GO protections

Every report returns:

- `advisory_only: true`
- `execution_allowed: false`
- `live_trading_enabled: false`
- `execution_action: NO_EXECUTION`

## Explainability

Every allocation row includes a rationale explaining why the opportunity received shadow capital. Every skipped opportunity appears in recommendations with constraint reasons such as cash reserve, sector cap, broker cap, strategy cap, low score, RED status, or concentration limits.

## Why Advisory Only

Capital Allocation Intelligence is a review artifact. It can recommend how capital might be distributed after all upstream validation and intelligence layers have produced evidence, but it never approves, rejects, routes, sizes, submits, or arms a trade.

## Future Promotion Path

Future production use would require separate governance approval, formal capital-governor integration, live-readiness review, broker execution authority review, audit controls, and explicit operator authorization. This phase intentionally stops before any execution-path integration.
