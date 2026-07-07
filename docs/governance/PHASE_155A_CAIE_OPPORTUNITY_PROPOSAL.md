# Phase 155A - CAIE Opportunity Proposal Schema and Validator

## Scope

Introduce a canonical CAIE opportunity proposal schema and a fail-closed validator contract for allocation proposals.

## Delivered Files

- `backend/allocation/__init__.py`
- `backend/allocation/opportunity_proposal.py`
- `backend/allocation/opportunity_validator.py`
- `tests/test_phase155a_opportunity_proposal.py`

## Canonical Proposal Fields

Required fields:

- `proposal_id` (non-empty string)
- `symbol` (non-empty string; normalized uppercase)
- `asset_class` (`CRYPTO|FX|FUTURES|OPTIONS|EQUITIES`)
- `probability` (float in `[0,1]`)
- `confidence` (float in `[0,1]`)
- `expected_drawdown_pct` (float in `[0,1]`)
- `risk_score` (float in `[0,100]`)
- `requested_capital` (float `> 0`)

## Validation Behavior

- Fail closed on malformed payload type.
- Fail closed on missing required fields.
- Fail closed on malformed asset class values.
- Fail closed on invalid probability/confidence/drawdown/risk ranges.
- Fail closed on non-positive requested capital.
- Emit deterministic, ordered error reasons and codes.

## Safety Constraints Preserved

- No runtime wiring in this phase.
- No trade-gate behavior change.
- No broker/live execution behavior change.

## Validation

- Added focused phase tests in `tests/test_phase155a_opportunity_proposal.py` that cover:
  - valid proposal pass path
  - missing required fields
  - invalid probability/confidence/drawdown/risk values
  - negative requested capital
  - malformed asset class
  - deterministic error reasons
