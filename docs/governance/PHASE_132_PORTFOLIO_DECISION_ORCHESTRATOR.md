# Phase 132 Portfolio Decision Orchestrator

## Purpose

Phase 132 creates a canonical advisory package that combines the existing portfolio advisory stack into one deterministic portfolio decision summary.

The orchestrator consumes:

- Portfolio Intelligence
- Capital Rotation
- Adaptive Portfolio Manager
- Strategy Attribution
- Regime Allocation
- Portfolio Risk Committee
- Quantitative Metrics
- Market Regime Intelligence
- Policy Profile
- Recommendation Tracker

## Decision Pipeline

The pipeline gathers advisory engine outputs, checks for missing inputs, determines the most conservative overall status, and emits one package containing:

- decision id
- timestamp
- overall status
- portfolio recommendation
- confidence
- policy profile
- market regime
- portfolio health
- capital rotation
- risk committee summary
- quantitative summary
- explanations
- conflicting signals
- missing inputs

Missing or invalid advisory inputs force a red package with `PAUSE_NEW_TRADES`.

## Persistence

Generated advisory packages are persisted under `artifacts/portfolio/` for history, lookup, and summary reporting. Persistence is for advisory auditability only.

## Execution Authority Separation

The orchestrator does not submit orders, arm live trading, modify allocations, or alter risk gates. Unified Trade Gate, Runtime Supervisor, Capital Governor, RBAC, AntiBleedGuard, Portfolio Risk Committee, and broker controls remain separate authorities.
