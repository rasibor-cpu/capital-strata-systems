# Phase 155G — CAIE Controlled Promotion Framework

## Status

IMPLEMENTED — POLICY / GOVERNANCE ONLY

## Purpose

Phase 155G defines a fail-closed maturity/promotion policy for the Capital
Allocation Intelligence Engine (CAIE). It does not activate live trading or
change broker/execution authority.

## Promotion stages

1. `SHADOW_ONLY`
2. `ACTIVE_ADVISORY_10`
3. `ACTIVE_ADVISORY_25`
4. `ACTIVE_ADVISORY_50`
5. `ACTIVE_ALLOCATION_100`

These are CAIE policy-stage labels only. In particular,
`ACTIVE_ALLOCATION_100` is **not** broker execution authority.

## Promotion controls

Promotion requires all of the following:

- sufficient matched recommendation/outcome evidence;
- EV calibration error within the configured threshold;
- confidence calibration error within the configured threshold;
- explicit operator approval;
- explicit governance approval;
- one-stage-at-a-time progression.

If any gate fails, the current stage is retained and the decision is `BLOCKED`.

## Rollback and de-escalation

- An explicit rollback request immediately returns CAIE to `SHADOW_ONLY`.
- A safe de-escalation to a lower stage is permitted without promotion approval.
- Promotion stage changes do not bypass any canonical CSS risk or execution gate.

## Safety invariants

Every promotion decision keeps these fields false:

- `execution_allowed`
- `broker_execution_armed`
- `money_movement_allowed`
- `live_trading_authorized`

Phase 155G adds no order-submission, cancellation, transfer, withdrawal,
deposit, funding, fee-collection, or client-fund authority.

## Phase 155 completion boundary

Phase 155A-G now provides the full CAIE foundation from canonical proposal
validation through scoring, portfolio optimization, runtime shadow projection,
observational calibration, read-only API visibility, and controlled promotion
policy.

Any future change that would convert a CAIE policy stage into real broker or
capital authority requires a separate explicitly approved assignment and must
pass the existing CSS risk, margin, broker, governance, operator-approval, and
execution gates.
