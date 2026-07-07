# Phase 155B - CAIE EV and Risk-Adjusted Scoring Engine

## Scope

Introduce a deterministic, advisory-only CAIE scoring engine for already-validated opportunity proposals.

## Delivered Files

- `backend/allocation/caie_scoring_engine.py`
- `tests/test_phase155b_caie_scoring_engine.py`
- `docs/governance/PHASE_155B_CAIE_SCORING_ENGINE.md`
- `backend/allocation/__init__.py` (export only)

## Scoring Inputs

Validated proposal payload (from Phase 155A validator):

- `valid=True`
- `normalized.probability`
- `normalized.confidence`
- `normalized.expected_drawdown_pct`
- `normalized.risk_score`
- `normalized.requested_capital`

Optional context:

- `liquidity_score` in `[0,1]` (default `1.0`)
- `regime_alignment` in `[0,1]` (default `1.0`)

## Scoring Components

- Expected value: `EV = probability - expected_drawdown_pct`
- Confidence contribution: applied only when `EV > 0`
- Capital efficiency contribution: applied only when `EV > 0`
- Risk penalties:
  - drawdown penalty from `expected_drawdown_pct`
  - risk penalty from `risk_score`
- Market quality contributions:
  - liquidity contribution from `liquidity_score`
  - regime contribution from `regime_alignment`

## Fail-Closed Rules

- Non-mapping input fails closed.
- Unvalidated input (`valid != True`) fails closed.
- Missing normalized payload fails closed.
- Out-of-range values fail closed.
- Non-positive requested capital fails closed.

## Determinism and Safety

- Output is deterministic and rounded.
- Output is advisory/shadow only:
  - `advisory_only=True`
  - `shadow_mode=True`
  - `execution_action=NO_EXECUTION`
- No runtime wiring added.
- No unified trade gate changes.
- No broker/live execution behavior changes.

## Validation

`tests/test_phase155b_caie_scoring_engine.py` covers:

- positive EV scores higher than negative EV
- confidence only boosts score when EV is positive
- high drawdown/risk reduce score
- low liquidity reduces score
- poor regime alignment reduces score
- capital efficiency improves score for positive EV
- invalid/unvalidated inputs fail closed
- deterministic scoring output
- advisory/shadow-only output contract
