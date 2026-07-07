# Phase 155C - CAIE Portfolio Ranking and Optimizer Shadow Layer

## Scope

Add a shadow-only portfolio optimizer that ranks validated/scored opportunities and recommends advisory capital allocations without any runtime execution wiring.

## Delivered Files

- `backend/allocation/caie_portfolio_optimizer.py`
- `tests/test_phase155c_caie_portfolio_optimizer.py`
- `docs/governance/PHASE_155C_CAIE_PORTFOLIO_OPTIMIZER.md`
- `backend/allocation/__init__.py` (exports only)

## Inputs and Validation

Optimizer accepts only opportunities that include:

- a Phase 155A validated proposal payload (`proposal.valid=True`, `proposal.normalized` present)
- a Phase 155B scoring payload (`score.valid=True`, numeric `score.score`)
- broker identifier (`broker`)

Invalid, unvalidated, or unscored payloads fail closed.

## Responsibilities Implemented

1. Rank opportunities by advisory score.
2. Respect available capital limit.
3. Respect per-asset-class capital caps.
4. Respect per-broker capital caps.
5. Apply concentration penalty using HHI-based concentration metrics.
6. Prefer diversification through objective bonus when adding new asset classes/brokers.
7. Hold cash when opportunities do not meet minimum quality score.
8. Produce deterministic ordering and deterministic output.

## Output Contract

The optimizer returns an advisory recommendation object with:

- `ranked_opportunities`
- `selected_opportunities`
- `recommended_capital_allocations`
- `unused_capital`
- `portfolio_score`
- `diversification_score`
- `concentration_metrics`
- `advisory_only = true`
- `shadow_mode = true`
- `execution_action = NO_EXECUTION`

## Safety and Non-Interference

- No runtime wiring.
- No broker behavior changes.
- No unified trade gate changes.
- No execution path changes.
- Shadow/advisory output only.

## Validation Coverage

`tests/test_phase155c_caie_portfolio_optimizer.py` covers:

- single opportunity
- multiple ranked opportunities
- insufficient capital
- broker cap reached
- asset-class cap reached
- concentration penalty
- hold-cash scenario
- deterministic ordering
- invalid input fail-closed behavior
- advisory/shadow-only output contract
