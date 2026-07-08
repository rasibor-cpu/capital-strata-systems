# Phase 47E/F: Broker Performance Intelligence and Decision Confidence

## Purpose

Phase 47E/F adds a deterministic, advisory-only broker intelligence layer for broker review and live-readiness evidence. It scores broker performance quality and evaluates the confidence behind broker-related decisions without changing execution, broker adapters, R7 gates, RBAC, startup gates, or NO-GO protections.

## Advisory-Only Scope

The Phase 47E/F modules are read-only analytics components under `backend/analytics`. The dashboard runtime exposes the combined report at `/api/v1/broker-performance-intelligence`.

The report always includes:

- `advisory_only: true`
- `execution_allowed: false`
- `live_trading_enabled: false`

No broker connection is opened by this phase. No order is submitted. No runtime execution path is authorized or bypassed.

## Broker Performance Inputs

Broker Performance Intelligence evaluates:

- Execution quality
- Spread and slippage profile
- Rejection and error frequency
- Latency or responsiveness
- Data availability
- Operational readiness
- Recent reliability trend
- Paper/live mode suitability

The output includes broker identity, overall score, GREEN/AMBER/RED status, strengths, weaknesses, recommended use, blockers, and a plain-language explanation.

## Decision Confidence Inputs

The Decision Confidence Framework evaluates:

- Broker readiness
- Broker credential and diagnostic quality
- Recent broker performance intelligence score
- Input completeness
- Runtime health
- Trade gate alignment
- Account and balance visibility
- Live-readiness constraints

Confidence bands are:

- `HIGH`: strong paper-mode confidence with complete inputs
- `MEDIUM`: usable for monitoring but not strong enough for promotion
- `LOW`: insufficient or weak evidence
- `BLOCKED`: a safety blocker, live-mode request, closed gate, RED broker score, or missing live authority prevents proceeding

Decisions are:

- `PROCEED_PAPER`
- `MONITOR`
- `DO_NOT_PROCEED_LIVE`
- `BLOCKED`

## Safety Protections

Phase 47E/F does not remove, weaken, or replace:

- R7 trade gates
- RBAC controls
- Broker startup gates
- Live-readiness certification
- NO-GO protections
- Broker execution firewalls
- Unified Trade Gate behavior

Live-mode decisions are intentionally blocked unless separate, existing live-execution authority says otherwise. Even then, this framework remains advisory evidence only and does not grant authority.

## Why This Does Not Authorize Live Trading

The framework returns confidence and intelligence, not execution authorization. Its payload explicitly sets `execution_allowed` to false and `live_trading_enabled` to false. The live-readiness and broker execution authority systems remain the only valid sources for live execution approval.

## Future Use

This phase supports future broker selection and live-readiness reviews by producing consistent evidence about broker quality, reliability, data completeness, and decision confidence. It can help compare brokers and identify blockers before an operator enters a formal live-readiness process, while preserving the existing fail-closed safety architecture.
