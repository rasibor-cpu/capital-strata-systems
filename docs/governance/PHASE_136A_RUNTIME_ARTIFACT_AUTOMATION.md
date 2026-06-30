# Phase 136A Runtime Artifact Automation

Phase 136A adds a canonical runtime artifact publisher for paper-runtime operations.
It is operational hardening only and does not introduce strategies, broker calls, live trading, credential handling, auto-login, or execution authority.

## Canonical Artifact Model

The runtime publisher writes advisory-only JSON artifacts under `artifacts/`:

- `css_account_state_pcnrass.json`
- `runtime_portfolio_state.json`
- `runtime_advisory_snapshot.json`
- `portfolio_snapshot.json`
- `portfolio_decision.json`
- `validation_summary.json`

Each published artifact includes:

- `timestamp`
- `runtime_cycle`
- `schema_version`
- `source_module`
- `advisory_only: true`
- `execution_allowed: false`

## Runtime Artifact Publisher

`backend/runtime/runtime_artifact_publisher.py` exposes `RuntimeArtifactPublisher.publish()`.
Runtime-cycle callers can provide already-computed portfolio state, advisory snapshot, decision package, and validation summary.
When data is missing, the publisher emits fail-closed advisory payloads rather than execution instructions.

Dashboard GET endpoints do not call the publisher with persistence. Runtime refresh automation must invoke publishing explicitly from a runtime cycle.

## Artifact Freshness States

`RuntimeArtifactFreshnessManager` reports:

- `FRESH`
- `AGING`
- `STALE`
- `MISSING`
- `NO_RECENT_TRADES`

Each artifact includes seconds old, threshold, freshness percentage, and status. Thresholds vary by artifact type so account state, portfolio state, validation summary, advisory snapshots, supervisor state, and closed trade ledger can age independently.

## Fail-Closed Behavior

Artifact read/write failures become warnings or degraded advisory status.
They must not cause HTTP 500 responses from dashboard APIs.
They must not trigger broker interaction, live execution, RBAC bypass, credential storage, or automatic login.

