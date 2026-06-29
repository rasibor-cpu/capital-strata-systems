# Phase 130 Portfolio Risk Committee

## Purpose

The Portfolio Risk Committee combines advisory portfolio evidence into one deterministic committee decision:

- Portfolio Intelligence
- Capital Rotation
- Adaptive Portfolio Management
- Strategy Attribution
- Regime-Aware Allocation
- Runtime supervisor and risk flags

## Advisory-Only Design

The committee output is a governance recommendation. It does not execute trades, approve broker requests, or mutate any live allocation/risk state.

Supported committee decisions are:

- `APPROVE_ADVISORY`
- `APPROVE_WITH_CAUTION`
- `REJECT_RISK_INCREASE`
- `PAUSE_NEW_TRADES`

All decisions include `advisory_only: true`.

## Fail-Closed Rules

Any critical safety flag, unavailable committee input, red adaptive status, or pause recommendation forces:

- `committee_status: RED`
- `committee_decision: PAUSE_NEW_TRADES`
- confidence at or below 30
- required actions explaining why new trade initiation should remain paused

Conflicting evidence lowers confidence and prevents risk expansion.

## Use Of Phase 129D And Phase 130 Engines

The committee consumes Phase 129D Portfolio Intelligence and Capital Rotation outputs directly. It also uses Phase 130 Adaptive Portfolio Management, Strategy Attribution, and Regime-Aware Allocation outputs to form a single explainable view.

The committee does not recalculate broker authority, trading permissions, or risk-gate outcomes.

## Execution Authority Separation

The committee does not weaken or bypass:

- Unified Trade Gate
- Capital Governor
- Runtime Supervisor
- RBAC
- AntiBleedGuard
- broker execution controls

Existing CSS governance remains the only authority for execution behavior. Phase 130 only adds portfolio-level advisory visibility.
