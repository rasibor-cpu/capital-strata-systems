# Phase 134A Operational Observability

## Purpose

Phase 134A adds an operational observability layer for CSS runtime monitoring, telemetry, diagnostics, and dashboard visibility.

This phase is monitoring-only. It does not add trading strategies, portfolio intelligence, broker execution changes, live trading capability, or governance modifications.

## Runtime Telemetry

The runtime performance monitor summarizes:

- advisory pipeline latency
- dashboard context latency
- API endpoint latency
- JSON persistence latency
- artifact read and write counts
- cache hit and miss rates
- average, peak, and rolling execution times
- memory usage when available
- CPU usage on a best-effort basis

Telemetry fails closed to a red operational status when required input is unavailable.

## Session Validation

The session validation engine checks:

- runtime duration
- restart and recovery counts
- stale artifacts
- stale dashboard state
- stale advisory package state
- persistence health
- recommendation stability
- policy consistency
- runtime heartbeat age

Stale heartbeat, missing session state, unhealthy persistence, or inconsistent policy evidence returns red session status.

## Health Aggregation

The runtime health aggregator combines:

- runtime performance status
- session validation status
- Runtime Supervisor status
- portfolio decision status

The most conservative status wins. Red in any critical source produces red operational health.

## Dashboard And API

The mobile dashboard now includes an Operational Health section showing runtime health, session status, latencies, cache hit rate, heartbeat age, restart and recovery counts, memory usage, CPU usage, and overall health.

Read-only endpoints:

- `GET /api/runtime-performance`
- `GET /api/session-validation`
- `GET /api/runtime-health`

These endpoints do not persist data, interact with brokers, execute trades, or modify runtime decisions.

## Advisory-Only Operation

Phase 134A preserves advisory-only architecture. It does not weaken Unified Trade Gate, Runtime Supervisor, Capital Governor, RBAC, AntiBleedGuard, Portfolio Risk Committee, or any risk gate.

## Fail-Closed Behaviour

Missing or malformed telemetry returns `DATA UNAVAILABLE` with red operational status. Dashboard rendering uses `DATA UNAVAILABLE` fallback for unavailable operational telemetry.
