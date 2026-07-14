# Phase EI-001 - Options Enterprise Integration

Date: 2026-07-14

Branch: `css-unified-consolidation-2026-07-13`

Classification: Read-Only / Paper-Safe / Pre-RC1

## Scope

Phase EI-001 integrates the Options Income Engine into the broader CSS enterprise architecture as a first-class paper/advisory subsystem. It does not add options trading logic and does not enable live trading, broker writes, order routing, execution arming, or production deployment.

All EI-001 payloads preserve:

- `paper_only=true`
- `advisory_only=true`
- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`

## Architecture Reviewed

EI-001 follows the architectural review in `docs/architecture/CSS_OPTIONS_INCOME_ENGINE_ARCHITECTURE_REVIEW.md` and integrates OI-002 through OI-010 with enterprise runtime, event, audit, dashboard, risk, alert, explainability, learning, derivatives, and certification surfaces.

## Enterprise Systems Reused

EI-001 reuses existing CSS patterns and models:

- Enterprise event bus model from `backend/events/event_models.py` and `backend/events/event_bus.py`.
- Enterprise alert severity/type model from `backend/monitoring/css_alert_models.py`.
- Enterprise certification readiness model from `backend/certification/readiness_models.py`.
- Existing OI-008 dashboard payload builders and OI-010 certification outputs.
- Existing OI-007 risk and Greeks payloads.
- Existing unified execution behavior, which continues to reject live options mode.

## Adapters Created

EI-001 adds adapter modules under `backend/options`:

- `options_income_enterprise_adapter.py`
- `options_income_runtime_registration.py`
- `options_income_event_adapter.py`
- `options_income_audit_adapter.py`
- `options_income_dashboard_adapter.py`
- `options_income_alert_adapter.py`
- `options_income_explainability_adapter.py`
- `options_income_learning_adapter.py`
- `options_income_certification_adapter.py`

These adapters normalize existing OI outputs into enterprise-shaped payloads. They do not create a new runtime process, event bus, audit store, dashboard server, certification engine, broker adapter, or execution route.

## Shared Services Introduced

EI-001 adds read-only shared derivatives services under `backend/derivatives`:

- `derivatives_exposure_service.py`
- `derivatives_stress_service.py`
- `derivatives_volatility_service.py`

These services normalize derivatives exposure, stress, and volatility evidence for future options, futures, structured product, convertible, and other derivatives integrations. They do not replace OI-007 behavior.

## Runtime Registration

`options_income_runtime_registration.py` registers Options Income as a canonical non-executable subsystem with deterministic capabilities, dependencies, health, readiness, heartbeat, success/failure fields, and certification status.

Registration is idempotent and restart-safe. Duplicate conflicting registrations fail closed.

## Event Integration

`options_income_event_adapter.py` converts OI lifecycle, risk, dashboard, alert, readiness, and certification milestones into deterministic enterprise event payloads. Events include stable IDs, ordering, correlation IDs, entity IDs, source module, audit metadata, and paper-only posture.

The adapter can publish into a caller-provided enterprise event bus. It does not add consumers and cannot mutate broker state.

## Audit Integration

`options_income_audit_adapter.py` builds immutable, append-only audit records for decisions, inputs, outputs, rules evaluated, supporting metrics, warnings, failures, unavailable data, source modules, certification evidence, safety posture, timestamps, and correlation IDs.

It appends only to caller-provided audit collections. It does not create a parallel persistent audit store and rejects missing audit frameworks.

## Dashboard Integration

`options_income_dashboard_adapter.py` registers read-only enterprise dashboard sections for summary, opportunities, paper positions, rolling recommendations, portfolio, income targets, Greeks, risk budgets, risk limits, assignment exposure, volatility risk, stress testing, alerts, certification, runtime health, and operational readiness.

It reuses OI-008 payloads and does not create a server, order-entry controls, trading buttons, or broker actions.

## Risk Integration

`options_income_enterprise_adapter.py` exposes `build_enterprise_risk_contribution`, which normalizes OI-007 outputs into an advisory enterprise risk contribution with asset class `OPTIONS`, subsystem `OPTIONS_INCOME`, Greeks, collateral utilization, assignment exposure, concentration, stressed loss, risk status, approval status, limit breaches, warnings, and unavailable data.

Risk integration is advisory only and never authorizes execution.

## Alert Integration

`options_income_alert_adapter.py` maps OI alerts into enterprise alert severity and type fields while preserving alert ID, category, message, reason, supporting metrics, affected entities, timestamp, acknowledgment state, and safety posture.

No external notifications are sent by EI-001.

## Explainability Integration

`options_income_explainability_adapter.py` adapts OI explanations into an audit-compatible enterprise explanation schema with decisions, summaries, primary reasons, supporting metrics, rules evaluated, warnings, unavailable inputs, source modules, correlation IDs, audit references, and safety posture.

## Learning Feedback

`options_income_learning_adapter.py` creates read-only learning observations from completed paper outcomes such as ranking outcome, premium captured, position duration, assignment outcome, roll outcome, capital efficiency, income target achievement, risk-limit outcome, stress-test result, portfolio performance, and certification result.

The adapter explicitly reports that it does not mutate strategy weights, execution thresholds, risk limits, broker settings, or production models.

## Certification Registration

`options_income_certification_adapter.py` maps OI-010 certification into enterprise subsystem certification evidence. It exposes module results, integration score, determinism score, paper safety score, dashboard score, broker abstraction score, documentation score, readiness, warnings, failures, unsupported features, and safety gates.

It does not mark the full platform RC1-certified.

## Operational Snapshot

`build_enterprise_operational_snapshot` combines runtime registration, dashboard, risk, alerts, certification, events, audit, and learning feedback into a canonical read-only operational snapshot with health, readiness, certification state, data freshness, event status, audit status, dashboard status, learning status, blockers, and warnings.

Valid operational states are `ONLINE`, `DEGRADED`, `OFFLINE`, and `UNAVAILABLE`.

Valid certification states are `NOT_REGISTERED`, `REGISTERED_PENDING_CERTIFICATION`, `PAPER_CERTIFIED`, `INTEGRATION_WARNING`, and `INTEGRATION_FAILED`.

No status authorizes live execution.

## Fail-Closed Behavior

EI-001 fails closed for missing registries, missing event bus, missing audit framework, duplicate subsystem/event/alert IDs, malformed timestamps, invalid or non-finite numeric values, stale data, live mode, execution-enabled posture, broker execution arming, order-capable payloads, broker-write capability, and unsafe learning mutation evidence.

## Safety Posture

EI-001 does not modify:

- live broker adapters
- broker authentication
- broker credentials
- tokens
- `.env`
- PEM files
- live order routing
- order submission
- order cancellation
- execution arming
- paper/live permission controls
- runtime databases
- Desktop-specific files
- production deployment configuration

## Out Of Scope

EI-001 does not implement:

- live options execution
- live broker activation
- live broker option-chain authority
- assignment execution
- roll order execution
- institutional live deployment
- full RC1 certification
- production deployment certification

## Validation Evidence

Validation run for EI-001:

- `python -m compileall backend/options backend/derivatives`
- `python -m pytest tests/test_ei001_options_enterprise_integration.py -q`

The EI-001 test suite covers runtime registration, duplicate registration, event payloads, event publication, event idempotency, audit adaptation, dashboard registration, risk contribution, derivatives exposure/stress/volatility, alert mapping, explainability adaptation, learning mutation prohibition, certification registration, operational snapshot, unsafe posture rejection, schema ordering, and unified execution live-options rejection.

## Known Limitations

EI-001 provides adapters and normalized evidence. It does not wire these adapters into a running server, start a runtime process, persist audit files, send notifications, or make dashboard routes executable in production.

## RC1 Integration Prerequisites

Before RC1 integration can rely on Options Income evidence:

- Enterprise certification must consume the EI-001 certification adapter output.
- Runtime dashboard snapshots must include the EI-001 operational snapshot.
- Event/audit persistence policy must approve Options Income event categories.
- Dashboard/mobile hosts must consume the read-only enterprise panels.
- Production certification must confirm no live options execution path is enabled.
