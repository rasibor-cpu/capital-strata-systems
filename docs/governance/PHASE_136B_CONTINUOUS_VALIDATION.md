# Phase 136B Continuous Validation

Phase 136B adds continuous validation and operational intelligence for long-duration paper-runtime sessions.
It remains advisory-only and cannot execute trades.

## Continuous Validation Monitor

`ContinuousValidationMonitor` combines:

- runtime health
- validation readiness
- session continuity
- artifact freshness
- runtime supervisor state
- portfolio lifecycle
- portfolio decision
- advisory snapshot

It returns a deterministic `GREEN`, `AMBER`, or `RED` validation state with warnings, blockers, and recommendations.

## Runtime Validation Metrics

`RuntimeValidationMetrics` calculates uptime, runtime cycles, cycle duration, dashboard/API latency, artifact write success rate, cache efficiency, supervisor recovery rate, restart frequency, validation degradation events, and recommendation stability trend.

Persistence is explicit. GET APIs use read-only evaluation.

## Runtime Health Trend

`RuntimeHealthTrend` maintains rolling 1-hour, 6-hour, and 24-hour trend summaries for runtime health, validation readiness, artifact freshness, session continuity, portfolio decision, and portfolio lifecycle.

## Validation Confidence

`ValidationConfidenceEngine` computes a deterministic confidence score and grade from runtime health, readiness, freshness, supervisor stability, session continuity, recommendation stability, portfolio decision, and runtime health trend.

## Long-Duration Validation

`LongDurationValidation` summarizes cumulative validation windows:

- 6 hours
- 12 hours
- 24 hours
- 48 hours
- 7 days

Summaries include uptime, restart count, recovery count, validation degradations, runtime health history, artifact health history, session continuity history, recommendation stability history, and paper performance summary.

## API And Dashboard Usage

Phase 136 adds GET-only APIs:

- `/api/runtime-validation-monitor`
- `/api/runtime-validation-metrics`
- `/api/runtime-health-trend`
- `/api/validation-confidence`
- `/api/long-duration-validation`

The mobile dashboard displays a Continuous Validation section with DATA UNAVAILABLE fallbacks.

## Safety

The framework has no broker authority, no live execution authority, no credential storage, and no automatic login.
All outputs include `advisory_only: true` and `execution_allowed: false`.

