# CSS Mission Control Architecture

## Product Vision

CSS Mission Control is the enterprise command, monitoring, governance, and
operational-intelligence interface for Capital Strata Systems. It is intended
to consolidate runtime, broker, portfolio, risk, certification, audit,
learning, and governance visibility into one institutional shell.

MC-001 is the foundation phase. It is read-only and does not become an
execution control plane.

MC-002 registers Mission Control with the existing dashboard web host and
connects the shell to canonical read-only runtime/dashboard payloads. It does
not create a second production server or change Desktop-specific runtime
behavior.

MC-003 connects Mission Control to the Desktop/mobile launcher runtime bridge
so the shell consumes actual runtime snapshot evidence when available and
fails closed to offline/unavailable state when the runtime is not active.

MC-004 binds Mission Control to the active runtime publisher used by
`scripts/css_live_dashboard.py`. It resolves existing runtime endpoint,
artifact, heartbeat, and cache evidence without starting another runtime
process or supervisor.

MC-005 adds the Institutional Operations Command Center projection layer. It
derives operational timeline, event stream, trade lifecycle, portfolio command,
broker telemetry, risk command, alert center, KPI, performance, Options Income,
system metrics, and source-consistency views from the canonical Mission Control
state. It remains read-only and does not add runtime controls.

MC-006 adds the Decision Intelligence projection layer. It derives decision
panel, trace, explanation, committee, counterfactual, recommendation, and
evidence-graph views from the canonical Mission Control state. It remains
advisory-only and cannot authorize trading.

MC-007A adds the Institutional Intelligence projection layer. It derives
strategy, opportunity, capital, attribution, committee, executive, and reporting
views from the canonical Mission Control state and upstream analytics evidence.
It remains read-only and does not create a new optimizer or authority path.

MC-007B adds the Secure Operations projection layer. It derives RBAC, operator,
approval, configuration, broker registry, feature flag, audit, change history,
rollback planning, and governance posture views from the canonical Mission
Control state. It remains locked and does not create write routes.

## Component Architecture

Mission Control is implemented as an additive dashboard package:

- `dashboard.mission_control.contracts`
- `dashboard.mission_control.state_adapter`
- `dashboard.mission_control.navigation`
- `dashboard.mission_control.layout`
- `dashboard.mission_control.routes`
- `dashboard.mission_control.app`
- `dashboard.mission_control.pages`
- `dashboard.mission_control.host_registration`
- `dashboard.mission_control.live_state_adapter`
- `dashboard.mission_control.source_registry`
- `dashboard.mission_control.freshness`
- `dashboard.mission_control.health`
- `dashboard.mission_control.permissions`
- `dashboard.mission_control.serializers`
- `dashboard.mission_control.runtime_snapshot_provider`
- `dashboard.mission_control.runtime_snapshot_normalizer`
- `dashboard.mission_control.runtime_bridge`
- `dashboard.mission_control.active_runtime_source`
- `dashboard.mission_control.runtime_source_resolver`
- `dashboard.mission_control.runtime_artifact_reader`
- `dashboard.mission_control.runtime_endpoint_reader`
- `dashboard.mission_control.runtime_source_diagnostics`
- `dashboard.mission_control.operations_timeline`
- `dashboard.mission_control.event_stream`
- `dashboard.mission_control.trade_lifecycle`
- `dashboard.mission_control.portfolio_projection`
- `dashboard.mission_control.broker_telemetry`
- `dashboard.mission_control.risk_projection`
- `dashboard.mission_control.system_metrics`
- `dashboard.mission_control.decision_intelligence`
- `dashboard.mission_control.decision_trace`
- `dashboard.mission_control.explanation_projection`
- `dashboard.mission_control.recommendation_projection`
- `dashboard.mission_control.counterfactual_projection`
- `dashboard.mission_control.committee_projection`
- `dashboard.mission_control.evidence_graph`
- `dashboard.mission_control.strategy_war_room`
- `dashboard.mission_control.opportunity_ranking`
- `dashboard.mission_control.capital_allocation`
- `dashboard.mission_control.performance_attribution`
- `dashboard.mission_control.executive_dashboard`
- `dashboard.mission_control.investment_committee`
- `dashboard.mission_control.risk_committee`
- `dashboard.mission_control.execution_committee`
- `dashboard.mission_control.capital_committee`
- `dashboard.mission_control.institutional_reporting`
- `dashboard.mission_control.rbac_console`
- `dashboard.mission_control.operator_console`
- `dashboard.mission_control.approval_workflow`
- `dashboard.mission_control.configuration_console`
- `dashboard.mission_control.broker_registry`
- `dashboard.mission_control.feature_flags`
- `dashboard.mission_control.audit_console`
- `dashboard.mission_control.change_history`
- `dashboard.mission_control.rollback_console`
- `dashboard.mission_control.governance_summary`

The package is mounted into `dashboard.web.web_app.create_app` through an
idempotent registration helper. The helper rejects conflicting
`/mission-control` routes and rejects write-capable methods.

The Desktop launcher host mounts Mission Control through
`launcher.css_mobile_launcher` with
`build_launcher_frontend_state` as the authoritative in-process runtime source.

## State Flow

State flow:

1. Existing runtime/dashboard payloads are provided to Mission Control.
2. `dashboard.runtime.frontend_contract.build_frontend_payload` normalizes the
   CSS frontend contract.
3. `dashboard.mission_control.state_adapter` adapts the frontend payload.
4. `dashboard.mission_control.contracts` builds
   `css.mission_control.state.v1`.
5. `dashboard.mission_control.source_registry` labels each section source and
   provenance.
6. `dashboard.mission_control.runtime_source_resolver` selects the active
   runtime source.
7. `dashboard.mission_control.runtime_snapshot_provider` resolves the current
   runtime snapshot.
8. `dashboard.mission_control.runtime_snapshot_normalizer` creates a
   canonical runtime snapshot with heartbeat and state hash.
9. `dashboard.mission_control.freshness` calculates deterministic freshness.
10. `dashboard.mission_control.health` derives display-only health.
11. MC-005 command-center projections derive read-only operational panels from
    the canonical Mission Control state.
12. MC-006 decision-intelligence projections derive read-only explanation,
    trace, recommendation, committee, counterfactual, and evidence graph panels
    from the same canonical state.
13. MC-007A institutional-intelligence projections derive strategy,
    opportunity, capital, attribution, committee, executive, and reporting
    panels from the same canonical state.
14. MC-007B secure-operations projections derive RBAC, workflow,
    configuration, registry, feature flag, audit, history, rollback planning,
    and governance panels from the same canonical state.
15. The shell renders all pages from the canonical Mission Control state.

Unavailable live data remains `UNAVAILABLE`. Mock data is explicitly labeled.

## Route Architecture

Mission Control exposes only read-only GET routes:

- `/mission-control`
- `/mission-control/{section}`
- `/mission-control/api/state`
- `/mission-control/api/health`
- `/mission-control/api/navigation`
- `/mission-control/api/page-metadata`
- `/mission-control/api/brokers`
- `/mission-control/api/certification`
- `/mission-control/api/runtime`
- `/mission-control/api/heartbeat`
- `/mission-control/api/runtime-source`
- `/mission-control/api/decision`
- `/mission-control/api/decision-trace`
- `/mission-control/api/explanation`
- `/mission-control/api/recommendation`
- `/mission-control/api/evidence`

There are no POST, PUT, PATCH, or DELETE operational routes in MC-002.

MC-003 and MC-004 preserve this GET-only route architecture.

## Runtime Snapshot Architecture

Mission Control runtime snapshot precedence is:

1. Shared runtime registry when explicitly marked cross-process safe.
2. Existing read-only localhost runtime endpoint when configured.
3. Existing current runtime artifacts produced by the desktop publisher.
4. Existing heartbeat and state artifacts.
5. Fresh cache.
6. Offline/unavailable fail-closed snapshot.

The canonical Desktop runtime publisher is
`scripts.css_live_dashboard.pcnrass_publish_runtime_artifacts`, which publishes
through `backend.runtime.runtime_artifact_publisher.RuntimeArtifactPublisher`.
The launcher bridge remains a read-only host integration surface; it is not
treated as a cross-process runtime registry unless the payload explicitly
declares that property.

## Runtime/Web-Host Separation

The web dashboard host may remain available when the trading runtime is offline.
In that condition Mission Control displays runtime offline and does not
substitute demo account, broker, portfolio, or market values.

## Demo Isolation

Demo/default dashboard values are accepted only when explicitly labeled as mock
or demo. Missing runtime data remains unavailable. The Executive Overview shows
a runtime-offline banner when current runtime evidence is absent.

## State Hash Consistency

Mission Control state, runtime API, and heartbeat API derive from the same
runtime snapshot during a refresh window. Runtime and heartbeat endpoints expose
the same runtime snapshot hash as the full state payload.

## Runtime Integration

Mission Control reuses existing runtime snapshots, frontend contracts,
certification snapshots, broker readiness state, and governance state. It does
not start a competing runtime server, event bus, supervisor, or persistence
loop.

## Source Registry

Each top-level Mission Control section exposes source metadata using:

- `LIVE`
- `RUNTIME`
- `RUNTIME_ENDPOINT`
- `RUNTIME_ARTIFACT`
- `RUNTIME_REGISTRY`
- `CACHE`
- `HISTORICAL`
- `MOCK`
- `DEMO`
- `UNAVAILABLE`
- `UNKNOWN`

The registry preserves source module, generated timestamp, observed timestamp,
provenance, and unavailable reason where known.

## Freshness Model

Freshness statuses are:

- `FRESH`
- `AGING`
- `STALE`
- `UNAVAILABLE`
- `UNKNOWN`

Mandatory stale or unavailable runtime, broker, certification, platform, or
safety data downgrades Mission Control health.

Runtime heartbeat freshness is mandatory. Stale or unavailable heartbeat state
downgrades Mission Control health.

MC-004 exposes runtime-source diagnostics with selected source, candidate
sources, artifact freshness, process relationship, fallback reason, and source
state hash.

MC-005 command-center widgets expose source, provenance, generated timestamp,
freshness, and runtime state hash. Source consistency is validated and hash
mismatches fail closed.

MC-006 decision-intelligence widgets expose the same source metadata and runtime
state hash. Committee contradictions, evidence-graph mismatches, and execution
language in recommendation actions fail closed.

MC-007A institutional-intelligence widgets expose source, provenance, generated
timestamp, freshness, runtime identifier, state hash, and decision hash.
Institutional panels participate in source-consistency validation.

MC-007B secure-operations widgets expose source, provenance, generated
timestamp, freshness, runtime identifier, and state hash. The panels participate
in source-consistency validation and fail closed on invalid permissions or
state mismatch.

## Operations Command Center

MC-005 adds read-only operational sections to the state contract:

- `operations_timeline`
- `event_stream`
- `trade_lifecycle`
- `portfolio_command`
- `broker_telemetry`
- `risk_command_center`
- `alert_center`
- `executive_kpis`
- `performance_panel`
- `options_income_panel`
- `system_metrics`
- `source_consistency`

These sections are projections of existing runtime, portfolio, broker, risk,
alert, certification, and learning sections. They do not introduce new runtime
state, broker calls, calculations with execution authority, or write-capable
controls.

## Decision Intelligence

MC-006 adds read-only decision intelligence sections to the state contract:

- `decision_panel`
- `decision_trace`
- `decision_explanation`
- `committee_view`
- `counterfactuals`
- `recommendation_panel`
- `evidence_graph`

These sections are projections of existing runtime, trading, portfolio, market,
risk, broker, audit, explainability, and learning evidence. They do not create
a second decision engine, alter confidence, override committees, allocate
capital, or trigger execution. Offline runtime state remains unknown/unavailable
and cannot produce synthetic approvals.

## Institutional Intelligence

MC-007A adds read-only institutional sections to the state contract:

- `strategy_war_room`
- `opportunity_ranking`
- `capital_allocation_center`
- `performance_attribution`
- `institutional_executive_dashboard`
- `investment_committee`
- `risk_committee`
- `execution_committee`
- `capital_committee`
- `institutional_reporting`

These sections adapt existing analytics, capital, portfolio, broker, risk,
audit, and committee evidence. They do not duplicate upstream calculations,
change committee outcomes, change allocation policy, or create an execution
control plane. Existing Mission Control pages render the panels as supporting
detail with links to related pages.

## Secure Operations

MC-007B adds read-only secure operations sections to the state contract:

- `rbac_console`
- `operator_console`
- `approval_workflow_console`
- `configuration_console`
- `broker_registry_console`
- `feature_flags_console`
- `audit_console`
- `change_history_console`
- `rollback_console`
- `governance_summary_console`

These sections adapt existing permissions, governance, broker, configuration,
audit, certification, and safety evidence. They do not add forms, write routes,
state-changing controls, credential workflows, broker mutation, or runtime
mutation. Existing governance, broker, configuration, audit, and certification
pages render the panels as supporting detail.

## Health Model

Mission Control health is display-only and may be:

- `GREEN`
- `AMBER`
- `RED`
- `UNAVAILABLE`
- `FAIL_CLOSED`

Unsafe safety flags or invalid contracts fail closed.

## Broker Integration

Broker Management consumes canonical broker runtime state, broker readiness,
status provenance, execution scope, failure reasons, and safety flags where
available.

Broker list support is a read-only foundation for:

- Coinbase
- OANDA
- IBKR
- paper/mock broker
- future adapters

Broker selection is preview-only in MC-001. Onboarding is a shell only.

MC-002 continues the same posture while displaying canonical broker readiness,
authentication, account, balance, buying power, market-data, latency,
provenance, and warning summaries when those fields are available upstream.

## Security Boundaries

Mission Control must not expose:

- secrets
- tokens
- PEM material
- private key paths
- JWT values
- broker credentials
- account identifiers unless explicitly redacted by upstream contracts

The state validator scans for secret-bearing payloads and fails closed.

MC-002 adds deterministic safe serialization and state hashing. Non-finite
numeric values and unsafe secret-bearing fields are rejected.

## RBAC Boundaries

MC-001 displays current user, role, unit, session, and permissions summaries
where available. It does not add user-management writes, role changes,
permission changes, or credential workflows.

MC-002 adds an explicit read-only permissions model:

- `read_only=true`
- `can_execute=false`
- `can_arm_broker=false`
- `can_modify_limits=false`
- `can_modify_credentials=false`
- `can_restart_runtime=false`
- `can_shutdown_runtime=false`
- `can_change_broker=false`

Future write workflows must remain subordinate to the existing RBAC,
live-operator wizard, R7 execution gates, execution firewall, and broker
authority layers.

## Responsive Architecture

The shell uses CSS-native responsive layout:

- persistent left navigation on desktop
- stacked navigation on tablet/mobile
- responsive metric grids
- responsive panel grids
- accessible landmarks and labels

No heavy frontend framework is introduced in MC-001.

## Future Control-Plane Design

Future control-plane features may include approval-gated runtime actions,
broker onboarding, incident workflows, and operator runbooks. These features
must be implemented only after explicit approval and must never bypass:

- R7 execution gates
- RBAC
- broker startup gates
- NO-GO logic
- live execution firewall
- execution boundary validation
- broker readiness/certification

## Future Secure Broker Onboarding

Future onboarding should separate:

- provider selection
- adapter type
- environment
- credential requirements
- permissions
- account requirements
- market-data requirements
- readiness checklist
- certification evidence

Credential entry and storage must use a secure future workflow. Browser state
must not store raw credential values.

## Future Deployment Strategy

MC-001 is developed on Laptop1. Desktop runtime deployment requires explicit
approval. Future phases should mount Mission Control into the approved runtime
surface only after regression, security, and governance validation.

MC-002 remains a Laptop1 host-registration and read-only integration phase.
Desktop synchronization and runtime validation remain separate approval-gated
steps.
