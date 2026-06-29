# Phase 135A Continuous Paper Trading Validation

## Purpose

Phase 135A adds a continuous paper-trading validation framework for controlled long-duration CSS sessions. The framework collects and summarizes validation evidence so operators can evaluate runtime health, paper-session continuity, advisory stability, and operational telemetry over time.

This phase is validation-only. It does not add trading strategies, modify broker execution, enable live trading, or change governance authority.

## Paper-Only Design

All Phase 135A outputs are marked advisory-only and paper-validation-only. The validation framework evaluates evidence; it does not place orders, change portfolio decisions, override gates, or alter Runtime Supervisor behavior.

## Readiness Model

The validation readiness engine determines whether CSS is ready to begin or continue a long paper session.

Inputs include:

- runtime health
- session validation
- portfolio decision status
- operational telemetry
- stale artifacts
- recent errors

Readiness output is:

- `READY`
- `READY_WITH_CAUTION`
- `NOT_READY`

Confidence is scored from 0 to 100. Blockers reduce confidence more heavily than warnings.

## Checkpoint Persistence

Validation checkpoints are persisted under `artifacts/validation/` by `SessionCheckpointStore`.

Supported operations:

- append checkpoint
- list checkpoints
- summarize session
- safely handle missing checkpoint files
- safely handle corrupt checkpoint files

GET dashboard/API endpoints are read-only and do not create checkpoints. Checkpoint persistence requires the explicit POST endpoint.

## Dashboard And API Usage

Read-only endpoints:

- `/api/validation-readiness`
- `/api/paper-validation-summary`
- `/api/paper-validation-checkpoints`

Explicit persistence endpoint:

- `/api/paper-validation-checkpoint/record`

The mobile dashboard adds a Paper Validation section showing readiness, validation status, session duration, cycle count, restart count, recovery count, alert count, error count, recommendation stability, latency summary, blockers, warnings, and `DATA UNAVAILABLE` fallback when checkpoint evidence is absent.

## Validation Status

`GREEN` means runtime health and portfolio decision status are healthy, no errors or stale artifacts are observed, recommendation stability is acceptable, and latency remains within target.

`AMBER` means validation can continue with caution because warnings exist, such as degraded runtime health, restarts, recoveries, alerts, stale artifacts, moderate recommendation instability, or elevated latency.

`RED` means validation evidence is not acceptable because critical runtime health, portfolio decision status, errors, stale artifacts, restarts, low recommendation stability, or latency blockers are present.

## No Live-Trading Authority

Phase 135A provides operational evidence for paper validation only. It has no authority to enable live trading, change broker execution, weaken risk gates, modify Unified Trade Gate decisions, or alter Capital Governor behavior.
