# Phase MC-007A - Mission Control Institutional Intelligence

## Purpose

Phase MC-007A completes the read-only institutional intelligence layer in CSS
Mission Control. It adds CIO-style portfolio, strategy, opportunity, capital,
committee, attribution, and reporting projections for operational visibility.

The phase adapts existing Mission Control, analytics, committee, portfolio,
risk, broker, audit, and decision-intelligence evidence. It does not create a
new optimizer, strategy engine, broker path, or authority path.

## Added Projections

- Strategy War Room
- Opportunity Ranking
- Capital Allocation Center
- Performance Attribution
- Institutional Executive Dashboard
- Investment Committee
- Risk Committee
- Execution Committee
- Capital Committee
- Institutional Reporting

Each projection includes source, provenance, generated timestamp, freshness,
runtime identifier, state hash, and decision hash when available.

## State Flow

1. Existing dashboard/runtime payloads are normalized by the frontend contract.
2. Mission Control builds its canonical state contract.
3. MC-005 operational projections and MC-006 decision projections are generated.
4. MC-007A institutional projections reuse the same state and upstream
   analytics sections.
5. Source consistency validates runtime hash alignment across the new panels.

No projection performs broker calls, mutates runtime state, alters limits, or
changes committee outcomes.

## Fail-Closed Rules

Mission Control fails closed when:

- runtime evidence is unavailable
- source consistency fails
- hashes diverge across institutional projections
- demo/runtime mixing is detected
- non-finite values appear
- secret-bearing payloads appear
- any institutional panel reports fail-closed status

Offline runtime state produces unavailable or fail-closed institutional panels
rather than synthetic readiness.

## Safety Guarantees

MC-007A preserves:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

MC-007A is display-only. It never places broker requests, changes credentials,
changes risk controls, changes capital limits, changes strategy logic, restarts
runtime services, or grants trading authority.

## Governance Relationship

MC-007A remains subordinate to:

- R7 governance
- RBAC
- broker startup and readiness gates
- live execution firewall
- execution boundary validation
- NO-GO protections
- existing investment and risk committee logic

Institutional reports and committee panels are advisory summaries only.
