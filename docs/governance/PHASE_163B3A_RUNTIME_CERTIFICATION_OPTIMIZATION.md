# Phase 163B.3A - Runtime Certification Optimization

## Purpose

Phase 163B.3A consolidates runtime broker certification display around one canonical read-only snapshot. The snapshot is derived from the Phase 156B Live Connectivity Certifier and the Phase 156C Broker Health Monitor, then exposed consistently to Desktop, Mobile, Runtime API, and Launcher consumers.

This phase is advisory-only. It does not authorize trading, arm broker execution, submit orders, cancel orders, or modify broker state.

## Root Causes Addressed

- Dashboard views could display broker readiness, health, latency, and market-data freshness from separate Phase 155/156 projections.
- Phase 156C could invoke Phase 156B independently when runtime code needed both connectivity certification and health.
- Runtime displays lacked a single lightweight telemetry payload for certification duration, broker API read counts, cache hits, cache misses, and cycle duration.
- Launcher artifact-backed validation panels and Runtime API sections did not have a shared canonical snapshot field to compare against.

## Canonical Snapshot

The canonical snapshot is produced by `backend.runtime.runtime_certification_snapshot`.

It contains:

- Phase 156A readiness state from the Phase 156B report
- Phase 156B certification report
- Phase 156C health report
- Canonical certification value
- Canonical operational state
- Canonical latency values
- Canonical market-data freshness
- Cached broker capability information
- Advisory firewall assertions
- Runtime telemetry

All exposed payloads force:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

## Runtime Flow

1. Runtime calls the Phase 163B.3A snapshot helper for a broker and cycle.
2. The helper checks the per-cycle snapshot cache.
3. On cache miss, it invokes the Phase 156B Live Connectivity Certifier once.
4. Phase 156C health is evaluated with the already-built Phase 156B report injected, preventing duplicate certification work.
5. Broker capability evidence is cached for the runtime cycle.
6. The canonical snapshot is stored by broker, mode, and cycle.
7. Dashboard and API consumers project their broker panels from this snapshot.

Launcher display paths also build artifact-backed canonical snapshots from existing Phase 156B/156C reports so dashboard refreshes do not trigger broker traffic.

## Telemetry

Runtime diagnostics expose:

- `certification_execution_ms`
- `broker_api_calls_performed`
- `cache_hits`
- `cache_misses`
- `runtime_cycle_duration_ms`
- `certification_runs`
- cached snapshot count
- cached capability count

These metrics are operational diagnostics only. They do not imply execution authority.

## Dashboard Consistency

The frontend contract now includes a `runtime_certification_snapshot` section. Broker, broker operational status, Coinbase live validation, and OANDA live validation sections prefer this canonical snapshot when present. Older artifact and direct validation payloads remain supported for backward compatibility.

Runtime API and Launcher expose:

- `/api/v1/runtime-certification-snapshot`
- `/api/v1/runtime-certification-diagnostics`

## Governance

Phase 163B.3A preserves:

- R7 execution gates
- RBAC controls
- NO-GO protections
- live execution firewall
- broker startup selection
- broker credential diagnostics
- Phase 156A, 156B, and 156C advisory boundaries

The snapshot is a read-only certification display and diagnostics object. It never enables live trading and never bypasses any execution boundary.
