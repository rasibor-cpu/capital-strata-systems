# Phase 135B Portfolio Runtime Integration

## Purpose

Phase 135B wires existing portfolio advisory engines into the live paper runtime and dashboard feed path. The initial paper validation readiness check returned `NOT_READY` because the Portfolio Decision package failed closed with missing advisory inputs, including portfolio intelligence, capital rotation, quantitative metrics, market regime intelligence, strategy attribution, and adaptive portfolio evidence.

This phase integrates existing runtime artifacts into those advisory inputs. It does not add trading strategies, broker execution, live trading, or execution authority.

## Runtime Portfolio State Model

`RuntimePortfolioStateBuilder` builds a canonical read-only state package from existing local artifacts:

- account state
- session state
- open positions
- closed trade outcome history or ledger data
- runtime supervisor state
- paper runtime staleness metadata

The output includes account summary, normalized positions, closed trades, performance metrics, asset allocations, strategy metrics, market data, supervisor status, staleness, and fail-closed reasons.

If required runtime artifacts are missing or malformed, the builder returns `DATA UNAVAILABLE` with explicit reasons.

## Advisory Input Wiring

The launcher feed path now routes runtime-derived state into the existing advisory engines:

- portfolio intelligence
- capital rotation
- adaptive portfolio
- strategy attribution
- regime-aware allocation
- portfolio risk committee
- quantitative metrics
- market regime intelligence
- policy profile
- recommendation tracker

The Portfolio Decision package remains fail-closed. When sufficient paper runtime state exists, required advisory components receive real inputs and the decision package no longer reports missing inputs.

## Runtime Advisory Snapshot

`RuntimeAdvisorySnapshot` builds a canonical advisory snapshot containing:

- runtime state status
- portfolio decision status
- available advisory components
- missing advisory components
- component statuses
- missing input reasons

The snapshot is advisory-only and explicitly non-executable.

## Validation Readiness

Validation readiness now distinguishes:

- unhealthy runtime process
- missing portfolio advisory inputs
- partial advisory snapshot
- genuine portfolio decision RED due to risk
- portfolio decision RED due to missing data

This improves recommended actions without weakening fail-closed behavior.

## Dashboard And API

New read-only endpoints:

- `/api/runtime-portfolio-state`
- `/api/runtime-advisory-snapshot`

Updated read-only endpoints:

- `/api/portfolio-decision`
- `/api/runtime-health`
- `/api/validation-readiness`

The mobile dashboard now shows runtime portfolio state status, advisory snapshot status, available/missing advisory component counts, missing input reasons, and Portfolio Decision status.

## Verification

Example checks:

```text
curl http://localhost:8000/api/runtime-portfolio-state
curl http://localhost:8000/api/runtime-advisory-snapshot
curl http://localhost:8000/api/portfolio-decision
curl http://localhost:8000/api/validation-readiness
```

Expected behavior with sufficient paper runtime artifacts:

- runtime portfolio state returns `OK`
- advisory snapshot returns `OK`
- Portfolio Decision `missing_inputs` is empty
- validation readiness no longer blocks solely because advisory inputs are empty

Expected behavior with missing artifacts:

- runtime portfolio state returns `DATA UNAVAILABLE`
- advisory snapshot is `PARTIAL` or `DATA UNAVAILABLE`
- Portfolio Decision remains fail-closed
- validation readiness remains `NOT_READY`

## No Live-Trading Authority

Phase 135B is advisory integration only. It does not call brokers, submit orders, enable live trading, change Runtime Supervisor decisions, weaken Unified Trade Gate behavior, alter Capital Governor behavior, or make advisory output executable.
