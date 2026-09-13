# CSS Simulator & Academy — Phase 2

This increment extends the simulation-only foundation with five coupled capabilities:

1. lesson sequencing and prerequisite-based progression;
2. recommendation accept/reject/modify journaling;
3. a richer challenge catalog;
4. achievement history derived from completed challenges;
5. a canonical read-only simulator projection suitable for API/mobile consumers.

## Safety invariants

The projection declares:

- `mode=SIMULATION`
- `execution_allowed=false`
- `broker_execution_armed=false`
- `money_movement_allowed=false`

No live broker command, order-routing function, transfer, withdrawal, deposit, or funding method is introduced.

## Curriculum model

Lessons are ordered and may depend on prerequisite lesson IDs. A lesson is:

- `LOCKED` when prerequisites are incomplete;
- `AVAILABLE` when prerequisites are satisfied;
- `COMPLETED` when completion has been recorded.

This model is intentionally small and deterministic so later persistence can be layered on without coupling to live brokerage code.

## Recommendation decision journal

The journal records a learner's decision about a CSS recommendation:

- ACCEPT
- REJECT
- MODIFY

Outcome labels are:

- GOOD
- BAD
- UNKNOWN

The journal feeds decision-quality scoring but does not execute or modify a broker instruction.

## Challenge catalog

The default catalog covers:

- capital preservation;
- benchmark outperformance;
- drawdown control;
- decision quality.

These are training measurements, not guarantees of future investment performance.

## Achievement history

Completed challenge progress can be transformed into immutable achievement records with UTC award timestamps and explicit source provenance.

## Read-only projection

The projection provides portfolio, scoring, lesson, decision, challenge, achievement, and optional probabilistic forecast data. Decimal values are serialized as strings to avoid implicit floating-point rounding.

The projection contains no live credentials, account secrets, or executable broker actions.

## Future merge note

This branch is deliberately independent of the newer local QRO-002X/QRO-003X code. After the newer worktree is pushed, a thin adapter can map canonical QRO replay snapshots into this simulator without moving simulation actions into the broker boundary.
