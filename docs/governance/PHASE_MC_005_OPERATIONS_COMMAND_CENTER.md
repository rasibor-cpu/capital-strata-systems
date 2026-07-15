# Phase MC-005 - Institutional Operations Command Center

## Purpose

Phase MC-005 extends CSS Mission Control into a read-only institutional
operations command center. It enriches the existing Mission Control state with
operational timeline, lifecycle, portfolio, broker, risk, alert, performance,
Options Income, KPI, system-metric, and source-consistency views.

## Data Flow

All MC-005 views derive from the existing Mission Control state:

1. Active runtime source resolver selects the runtime source.
2. Runtime snapshot normalizer creates the canonical runtime snapshot.
3. Mission Control contract builds canonical runtime, portfolio, broker, risk,
   alert, certification, and learning sections.
4. MC-005 projection modules derive command-center panels from those sections.

MC-005 does not call brokers, mutate runtime state, or recalculate authority.

## Added Views

- Operations timeline
- Event stream
- Trade lifecycle
- Portfolio command view
- Broker telemetry
- Risk command projection
- Alert center
- Executive KPI board
- Performance panel
- Options Income command panel
- System metrics
- Source consistency verification

Each view includes source, provenance, generated timestamp, freshness, and
runtime state hash metadata.

## Fail-Closed Rules

Mission Control remains fail-closed when:

- runtime evidence is unavailable
- heartbeat evidence is stale
- source hashes diverge
- demo/runtime mixing is detected
- non-finite values appear
- secret-bearing payloads appear
- safety flags are invalid

## Safety Guarantees

MC-005 preserves:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

MC-005 never submits orders, cancels orders, arms execution, edits credentials,
changes limits, changes risk gates, restarts runtime, or changes engine mode.

## Operational Scope

The command center is for visibility only. It supports institutional runtime
operations by consolidating existing evidence into a dealing-room style display,
but it does not become an execution or control plane.
