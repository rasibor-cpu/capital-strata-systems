# Phase 130 Adaptive Portfolio Management

## Purpose

Phase 130 adds an advisory-only Adaptive Portfolio Management layer. It synthesizes Phase 129D Portfolio Intelligence, Phase 129D Capital Rotation, runtime supervisor posture, and risk/governance context into a single portfolio-level recommendation.

## Advisory-Only Design

The adaptive portfolio manager produces recommendations only. It does not:

- submit broker orders
- change live trading mode
- alter Runtime Supervisor decisions
- alter Unified Trade Gate decisions
- alter Capital Governor decisions
- change portfolio allocation state
- bypass RBAC, AntiBleedGuard, or any risk gate

All output includes `advisory_only: true`.

## Separation From Execution Authority

Phase 130 is intentionally downstream of existing evidence and upstream of human or governance review. Recommendations such as `INCREASE_RISK`, `MAINTAIN`, `REDUCE_RISK`, and `PAUSE_NEW_TRADES` are advisory labels, not execution commands.

Any actual trading action remains governed by the existing CSS broker, runtime, trade gate, capital governor, RBAC, and risk-control layers.

## Fail-Closed Behavior

The adaptive manager fails closed when required inputs are missing, malformed, stale, or contradictory. Fail-closed output uses:

- `adaptive_recommendation: PAUSE_NEW_TRADES`
- `risk_committee_status: RED`
- confidence at or below 30
- clear risk flags and recommended actions

## Use Of Phase 129D

Phase 130 consumes Phase 129D outputs instead of duplicating calculations:

- Portfolio Intelligence provides portfolio health score, penalties, and concentration/downside metrics.
- Capital Rotation provides target allocation posture and defensive/balanced/opportunistic signals.

Phase 130 aggregates those outputs with runtime and governance context into a single explainable advisory recommendation.

## Broker And Live Execution Safety

No broker integration was added. No live execution switch was changed. No order placement path was introduced. The dashboard/API endpoints expose JSON summaries only and do not write trade-request artifacts.
