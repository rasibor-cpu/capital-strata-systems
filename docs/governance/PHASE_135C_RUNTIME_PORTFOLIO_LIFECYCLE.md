# CSS Phase 135C - Runtime Portfolio Lifecycle

## Purpose

Phase 135C maintains a canonical paper/advisory runtime portfolio view while the runtime is active. The lifecycle layer distinguishes a healthy startup with no open exposure from a broken runtime pipeline.

## Components

- `RuntimePortfolioLifecycle` builds the canonical lifecycle snapshot from runtime portfolio state, advisory snapshot, portfolio decision, and validation summary.
- `OpenPositionRegistry` tracks active paper/runtime positions under `artifacts/portfolio/` when explicitly invoked with persistence enabled.
- `RuntimeExposureBuilder` produces asset class, symbol, sector, strategy, directional, concentration, and diversification exposure views.

## Portfolio Lifecycle States

- `NO_PORTFOLIO`: runtime evidence is connected, but there are no open positions.
- `PARTIAL_PORTFOLIO`: runtime evidence is present but incomplete.
- `ACTIVE_PORTFOLIO`: runtime evidence is connected and open exposure exists.
- `BROKEN_PIPELINE`: required runtime evidence is missing or malformed.

Only `BROKEN_PIPELINE` is treated as a software integration blocker. `NO_PORTFOLIO` is a valid startup or flat-book state.

## Advisory-Only Operation

Phase 135C does not add strategies, submit orders, alter execution behavior, or modify live-trading authority. Dashboard and GET API endpoints are read-only. Lifecycle persistence is available only when explicit runtime code calls the lifecycle refresh with persistence enabled.

## Dashboard And API

The mobile dashboard includes a Runtime Portfolio panel with portfolio state, exposure, open position count, allocation, lifecycle status, artifact freshness, and runtime age. API reads include:

- `/api/runtime-portfolio-state`
- `/api/runtime-portfolio-lifecycle`
- `/api/runtime-advisory-snapshot`
- `/api/portfolio-decision`
- `/api/runtime-health`
- `/api/validation-readiness`

## Fail-Closed Behavior

Malformed or missing account/session runtime artifacts remain `DATA UNAVAILABLE` and map to `BROKEN_PIPELINE`. Healthy zero-position startup returns `LIMITED` or `NO_PORTFOLIO` where appropriate, allowing readiness and runtime health to avoid false RED status while preserving advisory-only safety.
