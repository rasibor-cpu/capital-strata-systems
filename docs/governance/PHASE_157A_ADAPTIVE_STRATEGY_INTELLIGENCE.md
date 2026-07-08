# Phase 157A - Adaptive Strategy Intelligence Framework

## Purpose

Phase 157A adds an advisory learning framework that evaluates which strategies
perform best under specific market regimes, asset classes, and confidence
levels.

This phase resumes the core CSS learning roadmap after the broker readiness
workstream. It does not modify broker behavior, execution gates, RBAC, existing
strategy engines, existing optimization logic, or the Decision Confidence
Framework.

## Learning Methodology

The framework consumes historical opportunity and outcome records. It groups
records by strategy, regime, asset class, and confidence bucket, then computes
strategy-level performance metrics and regime-specific effectiveness.

The learning output is advisory. It can recommend further review, monitoring,
or advisory confidence-weight changes, but it never applies those changes to
execution decisions.

## Metrics

For each strategy, Phase 157A tracks:

- total opportunities
- accepted opportunities
- rejected opportunities
- profitable trades
- losing trades
- average return
- median return
- win rate
- profit factor
- expectancy
- Sharpe
- Sortino
- maximum drawdown
- average holding period

## Regime Learning

The regime mapper normalizes and evaluates:

- Trending
- Ranging
- High volatility
- Low volatility
- Risk-off
- Risk-on

Each strategy/regime pair receives advisory evidence and a recommendation based
on sample size, return quality, win rate, and profit factor.

## Recommendations

Possible recommendations include:

- Increase confidence weighting
- Reduce confidence weighting
- Increase monitoring
- Temporarily suppress
- Needs additional evidence
- No advisory weighting change

These recommendations are evidence for human/runtime review only.

## Integration

Phase 157A can consume advisory context from:

- Decision Confidence
- Broker Performance Intelligence
- Opportunity Intelligence
- Existing learning modules

The integration payload records whether those sources were consumed. It also
explicitly reports that execution decisions and broker state were not changed.

## Governance

Phase 157A is strictly additive.

It never:

- authorizes execution
- arms brokers
- changes live trading state
- modifies R7 execution gates
- modifies RBAC
- changes broker subsystem behavior
- mutates existing learning or strategy engines
- changes existing optimization logic

All outputs preserve:

- `advisory_only=true`
- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `execution_authority_changed=false`

Phase 157A provides adaptive recommendations only. It NEVER authorizes
execution.
