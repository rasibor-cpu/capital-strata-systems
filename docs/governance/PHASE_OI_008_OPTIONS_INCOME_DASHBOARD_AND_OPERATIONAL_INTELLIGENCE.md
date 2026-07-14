# Phase OI-008 - Options Income Dashboard And Operational Intelligence

Date: 2026-07-14

Branch: `css-unified-consolidation-2026-07-13`

## Purpose

Phase OI-008 adds the canonical paper-only Options Income Dashboard and Operational Intelligence layer. It exposes the capabilities already implemented in OI-002 through OI-007 through deterministic read-only payload builders and API-route registration helpers.

This phase never creates orders, submits orders, cancels orders, routes execution, calls broker APIs, changes permissions, modifies live runtime state, or enables live trading.

## Architecture

The implementation is split into additive paper-only modules:

- `backend/options/options_income_dashboard.py` coordinates the canonical top-level dashboard payload.
- `backend/options/options_income_dashboard_payloads.py` normalizes OI-002 through OI-007 source payloads into dashboard-ready sections.
- `backend/options/options_income_operational_intelligence.py` reports deterministic operational status, module availability, data freshness, repository health, and payload health.
- `backend/options/options_income_alerts.py` creates read-only operational alerts.
- `backend/options/options_income_explainability.py` creates deterministic explanation records for opportunities, positions, rolls, portfolio allocation, risk, approvals, and alerts.
- `backend/options/options_income_api.py` exposes read-only API payload helpers and FastAPI router registration without creating a server.

## Dashboard Sections

The canonical payload contains:

- top-level engine summary
- opportunity intelligence
- active and completed paper positions
- advisory roll recommendations
- paper portfolio construction, capital, concentration, laddering, income targets, and rebalancing
- Greeks and risk intelligence
- deterministic stress-test display
- operational status
- alerts
- explainability

Every top-level payload and API response explicitly preserves:

- `paper_only=true`
- `advisory_only=true`
- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`

## Operational Intelligence

Operational status is deterministic and reports:

- module availability
- data freshness
- repository health
- scanner health
- lifecycle health
- position-manager health
- portfolio-engine health
- Greeks health
- risk-engine health
- stress-engine health
- API payload health
- last successful assessment
- last failed assessment
- failure reason
- stale-data reason
- certification status

Statuses are `ONLINE`, `DEGRADED`, `OFFLINE`, or `UNAVAILABLE`. No operational status authorizes execution.

## Alerts

Alerts are read-only and cover risk-limit breaches, assignment concentration, collateral utilization, missing Greeks or IV, stale data, repository corruption, rejected risk approval, income target shortfall, near-expiry positions, roll eligibility, and unsafe execution posture.

Severities are `INFO`, `WARNING`, and `CRITICAL`. Alerts never create automated actions.

## Explainability

Explanations are deterministic and auditable. They explain why an opportunity was accepted or rejected, why a position is healthy or unhealthy, why a roll was recommended, why a portfolio allocation was selected, why constraints were breached, why risk status was assigned, why paper approval was accepted or rejected, and why alerts were raised.

## Fail-Closed Behavior

OI-008 rejects or marks invalid:

- missing portfolio data
- duplicate paper positions
- malformed timestamps
- stale data
- invalid or non-finite numeric values
- negative capital, collateral, or premium
- unsupported strategies
- invalid lifecycle states
- repository corruption
- missing Greeks
- missing IV
- risk-governance failure
- live mode
- execution-enabled posture
- broker-dependent payloads

Fail-closed payloads preserve paper/advisory flags and surface deterministic error details.

## API And Dashboard Integration

`backend/options/options_income_api.py` provides read-only endpoint equivalents for:

- `/api/options-income/summary`
- `/api/options-income/opportunities`
- `/api/options-income/positions`
- `/api/options-income/rolls`
- `/api/options-income/portfolio`
- `/api/options-income/greeks`
- `/api/options-income/risk`
- `/api/options-income/stress-tests`
- `/api/options-income/alerts`
- `/api/options-income/explainability`
- `/api/options-income/operational-status`

The module registers routes against an existing FastAPI application when called by a host. It does not create an independent server.

## Mobile Dashboard Readiness

OI-008 provides mobile-ready read-only sections for summary, positions, income targets, portfolio utilization, Greeks, risk, assignment exposure, stress-test worst case, and alerts. It does not add trading buttons, order-entry controls, or live execution controls.

## Relationship To Prior Phases

OI-002 defines covered-call and cash-secured-put strategy summaries.

OI-003 provides accepted and rejected income opportunities.

OI-004 creates paper income lifecycle positions.

OI-005 manages paper positions, health, metrics, and rolling advisory.

OI-006 constructs paper income portfolios.

OI-007 assesses paper risk, Greeks, assignment, volatility, stress scenarios, and governance approval.

OI-008 exposes these outputs through canonical dashboard, alert, operational, explainability, and read-only API payloads.

## Out Of Scope

This phase does not implement broker integration, live order entry, live execution routing, assignment execution, production activation, institutional deployment, live certification, credential handling, runtime database mutation, or broker connectivity.
