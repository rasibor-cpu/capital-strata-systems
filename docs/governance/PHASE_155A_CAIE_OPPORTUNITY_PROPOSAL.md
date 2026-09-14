# Phase 155A — CAIE Opportunity Proposal Schema

## Status

IMPLEMENTED FOR SHADOW/ADVISORY USE

## Purpose

Phase 155A introduces the canonical Capital Allocation Intelligence Engine
(CAIE) opportunity proposal and its fail-closed validator.

It deliberately does **not** implement scoring, optimization, runtime
integration, dashboard visibility, promotion policy, broker submission, or
capital movement. Those are later phases and remain unimplemented by this
change.

## Canonical proposal fields

- proposal_id
- source
- broker
- symbol
- asset_class
- side
- probability_win
- confidence
- capital_required
- max_drawdown_pct
- expected_return_pct
- liquidity_score
- regime_alignment
- observed_at_utc

Monetary/risk/scoring inputs use `Decimal`. Observation timestamps must be
timezone-aware UTC.

Supported asset classes for this first schema are:

- EQUITY
- ETF
- FX
- CRYPTO
- FUTURES
- OPTIONS

## Validation posture

Validation fails closed for:

- missing fields;
- empty identifiers;
- malformed decimals;
- non-finite decimals;
- probability/confidence/score values outside [0, 1];
- non-positive required capital;
- drawdown outside [0, 1];
- unsupported/malformed asset classes;
- unsupported sides;
- naive or non-UTC timestamps.

## Safety boundary

This module is advisory data infrastructure only.

It adds no:

- order submission;
- order cancellation;
- broker mutation;
- execution routing;
- transfer;
- withdrawal;
- deposit;
- funding;
- client-fund authority;
- live-trading authorization.

Existing CSS gates, risk controls, broker controls, runtime supervision, and
fail-closed execution posture remain authoritative.

## Phase boundary

Per the approved Phase 155 issue, this commit stops at **155A**. Phase 155B
scoring must be separately implemented and validated after this foundation is
certified.
