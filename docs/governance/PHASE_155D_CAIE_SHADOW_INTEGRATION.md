# Phase 155D — CAIE Runtime Shadow Integration

## Status

IMPLEMENTED — ADVISORY / SHADOW ONLY

## Integration model

CAIE now has a runtime-safe shadow adapter and read-only runtime projection.

The adapter is invoked only after an existing canonical eligibility result is
supplied. A false eligibility result is authoritative and CAIE returns
`NOT_ELIGIBLE` without producing an allocation plan.

This preserves the existing trade gate as the authority boundary.

## Safe behavior

- Eligible opportunities can produce a shadow recommendation.
- No opportunities produce an explicit empty shadow result.
- CAIE exceptions are contained and projected as `UNAVAILABLE`.
- CAIE failure does not crash the caller.
- Runtime projection contains explicit false execution and money-movement flags.
- No active execution route is added.

## Non-authority

CAIE does not replace or bypass:

- CSSUnifiedTradeGate;
- Risk Governor;
- MarginTradeGate;
- capital controls;
- broker readiness;
- runtime supervisor;
- operator approval.

CAIE remains advisory only and cannot submit, modify, or cancel orders.

## Phase boundary

Phase 155D does not persist learning outcomes, expose an active dashboard route,
or create a promotion path. Those remain Phases 155E-155G.
