# Phase MC-006 - Mission Control Decision Intelligence

## Purpose

Phase MC-006 adds read-only decision intelligence to CSS Mission Control. It
projects existing decision evidence into operator-facing views for decision
status, traceability, explanation, committee posture, counterfactuals,
recommendations, and evidence graph consistency.

The phase explains CSS decisions. It does not make decisions, change strategy
logic, alter risk thresholds, or authorize execution.

## Data Flow

All MC-006 views derive from the canonical Mission Control state:

1. Existing runtime/dashboard payloads are normalized by the frontend contract.
2. Mission Control builds canonical runtime, trading, portfolio, market, risk,
   broker, audit, learning, governance, and safety sections.
3. MC-005 command-center projections enrich operational context.
4. MC-006 projection modules derive decision intelligence from the same state.
5. Source consistency validates runtime hash alignment across the projections.

No MC-006 module performs broker calls, submits requests to strategy engines, or
creates new execution authority.

## Added Views

- Decision panel
- Decision trace
- Decision explanation
- Committee view
- Counterfactual projection
- Recommendation panel
- Evidence graph

Each view carries source, generated timestamp, provenance, freshness, runtime
identifier, and runtime state hash metadata when available.

## API Surface

MC-006 adds GET-only endpoints:

- `/mission-control/api/decision`
- `/mission-control/api/decision-trace`
- `/mission-control/api/explanation`
- `/mission-control/api/recommendation`
- `/mission-control/api/evidence`

These endpoints return the same canonical state objects used by the desktop and
mobile Mission Control pages. There are no POST, PUT, PATCH, or DELETE routes.

## Fail-Closed Rules

Mission Control fails closed when:

- safety flags are not blocked/read-only
- source consistency fails
- committee outcomes are malformed
- evidence graph hashes diverge
- recommendations contain execution language
- non-finite values appear
- secret-bearing payloads appear

Offline runtime state produces unavailable/unknown decision intelligence rather
than synthetic approvals.

## Safety Guarantees

MC-006 preserves:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

MC-006 never submits orders, cancels orders, arms execution, edits credentials,
changes limits, changes risk gates, restarts runtime, changes engine mode, or
overrides investment committee, risk, broker, or R7 authority.

## Governance Relationship

MC-006 is subordinate to the existing CSS governance stack:

- R7 execution gates
- RBAC
- broker startup gates
- broker readiness and certification
- NO-GO protections
- live execution firewall
- execution boundary validation

Recommendations are advisory operator guidance only. They never create live or
paper execution capability.
