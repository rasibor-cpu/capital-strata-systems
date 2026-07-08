# Phase 156C - Continuous Broker Health Monitor

## Purpose

Phase 156C adds a continuous advisory health monitor for configured brokers.
It extends the Phase 153-156B broker governance framework by turning credential
diagnostics and controlled connectivity certification into rolling operational
health telemetry.

This module performs monitoring only. It never authorizes execution.

## Health Metrics

The monitor evaluates:

- credential status from broker credential diagnostics
- authentication status from Phase 156B connectivity certification
- connection availability and stability
- authentication, account, market-data, and overall latency
- rolling latency averages
- market-data freshness, missing quotes, and timestamp drift
- API health failures such as timeouts, DNS, TLS, network errors, rate limits,
  broker unavailable responses, clock skew, and authentication failure
- rolling success and failure percentages
- reconnect count
- last successful validation timestamp
- firewall integrity

Every output remains advisory-only and reports execution blocked.

## Scoring Model

The monitor produces `overall_health_score` on a 0-100 scale.

Default score inputs are:

- credential health
- authentication
- Phase 156B connectivity score
- latency
- market-data freshness
- API quality
- reliability
- firewall integrity

The resulting health state is:

- `GREEN` when the broker is healthy and inside configured thresholds
- `AMBER` when the broker is usable for monitoring but degraded
- `RED` when credentials, connectivity, freshness, API health, or firewall
  integrity fails closed

Thresholds are configurable through `BrokerHealthThresholds`.

## Trend Analysis

The monitor stores rolling in-memory samples per broker and reports:

- rolling latency
- rolling availability
- rolling reliability
- rolling API quality
- trend direction

Trend direction is:

- `IMPROVING` when the current health score materially improves
- `STABLE` when score movement is inside the configured trend band
- `DEGRADING` when the current health score materially weakens

Reconnect count increments when a broker moves from `RED` back to `GREEN` or
`AMBER`.

## Advisory Integrations

Phase 156C emits integration-ready advisory payloads for:

- Broker Performance Intelligence
- Decision Confidence Framework
- Opportunity Intelligence
- dashboard runtime status

These payloads are informational only. Existing modules remain unchanged and
retain their own advisory and execution-safety rules.

## Relationship To Prior Phases

Phase 156A remains the broker readiness validation foundation.

Phase 156B remains the controlled live connectivity certification source.

Phase 156C consumes those signals continuously and adds rolling health,
reliability, latency, API-quality, and trend awareness.

Broker startup selection, broker bootstrap, credential diagnostics, broker
readiness, execution boundary validation, live execution firewall, RBAC, NO-GO
protections, R7 governance, Decision Confidence, and Broker Performance
Intelligence remain authoritative in their existing domains.

## Firewall Verification

Every health report verifies:

- `execution_allowed == false`
- `live_trading_blocked == true`
- `broker_execution_armed == false`

If any upstream report suggests execution authority, the monitor fails closed
to `RED` and still emits blocked advisory fields.

## Safety Guarantees

Phase 156C must never:

- submit orders
- cancel orders
- modify broker state
- arm execution
- enable live trading
- bypass execution boundaries

The module provides continuous operational awareness only. It never authorizes
live execution.
