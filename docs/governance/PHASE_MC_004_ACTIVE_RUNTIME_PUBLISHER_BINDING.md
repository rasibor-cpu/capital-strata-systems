# Phase MC-004 - Mission Control Active Runtime Publisher Binding

## Purpose

Phase MC-004 binds Mission Control to the active CSS desktop runtime publisher
used by `scripts/css_live_dashboard.py`.

The phase is read-only. It does not start a second runtime process, supervisor,
heartbeat loop, broker process, event bus, or execution service.

## Runtime Publisher

The desktop runtime publishes operational evidence through:

- `scripts.css_live_dashboard.pcnrass_publish_runtime_artifacts`
- `backend.runtime.runtime_artifact_publisher.RuntimeArtifactPublisher`
- `backend.runtime.css_runtime_supervisor.CSSRuntimeSupervisor`

The active cross-process artifacts are:

- `artifacts/css_session_state_pcnrass.json`
- `artifacts/css_account_state_pcnrass.json`
- `artifacts/runtime_portfolio_state.json`
- `artifacts/runtime_advisory_snapshot.json`
- `artifacts/portfolio_snapshot.json`
- `artifacts/portfolio_decision.json`
- `artifacts/validation_summary.json`
- `runtime/supervisor/css_runtime_supervisor_state.json`

Mission Control reads these files only. It never mutates them.

## Source Precedence

Mission Control source resolution uses this precedence:

1. Shared runtime registry, only when explicitly cross-process safe.
2. Existing localhost runtime endpoint, only when configured and localhost.
3. Existing current runtime artifacts from the desktop publisher.
4. Existing heartbeat and state artifacts.
5. Fresh cache.
6. `UNAVAILABLE`.

Supported source labels are:

- `RUNTIME_ENDPOINT`
- `RUNTIME_ARTIFACT`
- `RUNTIME_REGISTRY`
- `CACHE`
- `HISTORICAL`
- `DEMO`
- `UNAVAILABLE`

## Diagnostics

The resolver reports:

- selected source
- candidate sources
- freshness
- artifact paths
- process relationship
- failure reason
- fallback reason
- state hash

The read-only API endpoint is:

- `/mission-control/api/runtime-source`

## Safety Guarantees

MC-004 preserves:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

It never submits orders, cancels orders, arms execution, changes broker state,
changes limits, edits credentials, or modifies runtime databases.

If no active source is available, Mission Control reports `UNAVAILABLE` and the
runtime snapshot fails closed to offline.
