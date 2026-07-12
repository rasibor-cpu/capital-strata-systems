# Phase 167 - Multi-Committee Institutional Decision Framework

## Purpose

Phase 167 evolves the Institutional Investment Committee from a single advisory decision engine into a multi-committee governance framework.

Each committee independently evaluates candidate opportunities. The IIC then aggregates their votes, confidence, explanations, vetoes, and capital implications into one institutional recommendation.

This phase remains advisory only and never authorizes execution.

## Committee Architecture

The framework adds:

- `committee_members.py` for independent advisory committees.
- `voting_engine.py` to run each committee vote.
- `committee_consensus.py` to aggregate votes into one institutional recommendation.
- `committee_history.py` to serialize decision history for explainability.

The six committee members are:

- Market Committee
- Risk Committee
- Capital Committee
- Portfolio Committee
- Liquidity Committee
- Operational Committee

Each committee returns:

- vote
- confidence
- committee score
- reason
- strengths
- weaknesses
- veto marker when applicable

## Voting Process

Supported committee votes:

- `APPROVE`
- `APPROVE_WITH_CAUTION`
- `WAIT`
- `REJECT`
- `ABSTAIN`

Votes are produced independently from the same normalized opportunity and portfolio context. A committee cannot grant execution authority.

## Consensus Model

The consensus engine supports:

- unanimous approval
- majority approval
- split committee
- veto conditions
- tie resolution
- weighted committee confidence

Final institutional recommendations include:

- `APPROVED`
- `APPROVED_LOW_PRIORITY`
- `WAIT`
- `REJECT`
- `CAPITAL_BETTER_DEPLOYED`
- `RISK_VETO`
- `PORTFOLIO_VETO`
- `LIQUIDITY_VETO`
- `OPERATIONAL_VETO`

## Veto Hierarchy

Vetoes are applied before capital competition:

1. `RISK_VETO`
2. `PORTFOLIO_VETO`
3. `LIQUIDITY_VETO`
4. `OPERATIONAL_VETO`

When a veto is present, capital competition cannot upgrade the opportunity to approved.

## Capital Competition

After consensus, qualified opportunities compete for finite advisory capital.

Higher-ranked opportunities can displace lower-ranked opportunities. Displaced opportunities receive `CAPITAL_BETTER_DEPLOYED`.

This remains a shadow recommendation and does not create trade requests.

## Dashboard

The dashboard now exposes:

- committee votes
- committee confidence
- committee explanations
- consensus score
- veto reasons
- final recommendation

The existing `institutional_investment_committee` section remains backward compatible while carrying additional vote and consensus fields.

## API

Existing endpoint:

- `/api/v1/institutional-investment-committee`

New vote-detail endpoint:

- `/api/v1/institutional-investment-committee/votes`

Both endpoints are advisory-only and return execution-blocked safety flags.

## Committee History

Committee history records:

- timestamp
- opportunity ID
- votes
- recommendation
- confidence
- consensus
- committee explanations

The default store is in-memory and side-effect free. It is intended for runtime explainability and testable serialization without writing broker or execution artifacts.

## Governance

Phase 167 does not modify:

- R7 execution gates
- RBAC
- broker subsystem
- live execution firewall
- execution boundary validation
- NO-GO protections

All reports preserve:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

## Future Extensibility

Future phases can add committee-specific calibration, persistent history, formal investment memos, stress tests, and human-review workflows. Any future extension must preserve advisory-only boundaries unless separately governed and approved.
