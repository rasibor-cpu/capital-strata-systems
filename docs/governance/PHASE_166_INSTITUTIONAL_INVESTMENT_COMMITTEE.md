# Phase 166 - Institutional Investment Committee

## Purpose

Phase 166 introduces the Institutional Investment Committee (IIC), the highest-level advisory trade selection engine in CSS.

The IIC does not generate trade signals. It evaluates candidate trades produced by existing systems and determines whether they deserve advisory capital allocation priority.

This phase is advisory only. It never authorizes execution.

## Architecture

The implementation lives in `backend/investment_committee/`:

- `committee_models.py` defines canonical decisions, opportunities, scorecards, evaluations, and reports.
- `committee_scorecard.py` scores each opportunity across institutional dimensions.
- `portfolio_context.py` builds portfolio and governance context from dashboard/runtime payloads.
- `capital_competition.py` ranks opportunities against finite deployable capital.
- `opportunity_ranking.py` provides deterministic ranking helpers.
- `committee_explainability.py` produces institutional explanations.
- `committee_dashboard.py` serializes report output for dashboard/runtime display.
- `investment_committee.py` orchestrates scoring, ranking, capital competition, and reporting.

## Committee Workflow

1. Candidate opportunities are normalized into a common committee model.
2. Portfolio context is derived from account, risk, position, market, and broker state.
3. Each candidate receives a scorecard.
4. Scorecards are ranked by committee score, capital efficiency, expected return, and symbol.
5. Capital competition assigns advisory capital only to the highest-ranking candidates that fit constraints.
6. Every opportunity receives a committee decision and explanation.
7. Runtime API and dashboard layers expose the output as read-only advisory state.

## Decision Model

Supported decisions:

- `APPROVED`
- `APPROVED_LOW_PRIORITY`
- `WAIT`
- `REJECT`
- `INSUFFICIENT_EDGE`
- `CAPITAL_BETTER_DEPLOYED`
- `RISK_LIMIT_EXCEEDED`
- `PORTFOLIO_CONFLICT`

The committee scorecard evaluates expected return, probability, drawdown, holding period, capital efficiency, correlation, concentration, asset allocation impact, regime suitability, liquidity, spread quality, execution cost, volatility, risk budget, strategy confidence, signal quality, historical similarity, decision confidence, operational readiness, and market health.

## Capital Allocation Process

Capital is finite. The committee ranks opportunities and allocates advisory capital to the best use of capital first.

An otherwise attractive trade can receive `CAPITAL_BETTER_DEPLOYED` when higher ranked opportunities consume the available budget or allowed committee slots.

The capital plan is a shadow recommendation only. It does not create trade requests and does not arm execution.

## Ranking Methodology

Opportunities are ranked by:

1. Committee score
2. Capital efficiency
3. Expected return
4. Symbol for deterministic tie-breaking

Risk and portfolio blockers cap the effective score and can force `RISK_LIMIT_EXCEEDED` or `PORTFOLIO_CONFLICT`.

## Explainability

Every evaluation includes an institutional explanation covering:

- expected return
- expected drawdown
- confidence
- capital efficiency
- correlation
- decision
- rank
- strengths
- weaknesses

Explanations state that the recommendation is advisory only and does not authorize execution.

## Dashboard And API

The runtime API exposes:

- `/api/v1/institutional-investment-committee`

The frontend state contains:

- `sections.institutional_investment_committee`

The web dashboard displays:

- committee score
- decision
- capital rank
- expected return
- expected drawdown
- confidence
- capital efficiency
- opportunity rank
- committee recommendation

## Governance

Phase 166 does not modify R7, RBAC, broker startup, broker certification, NO-GO controls, live execution firewall, or execution boundary validation.

All outputs preserve:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

The committee is a governance and selection layer, not an execution authority.

## Future Extensibility

Future phases can add more committee members, historical analog libraries, scenario stress tests, or investment memo exports. Those additions should continue to consume the IIC advisory output without granting execution authority.
