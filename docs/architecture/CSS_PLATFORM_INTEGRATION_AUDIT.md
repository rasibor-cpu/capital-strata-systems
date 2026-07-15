# CSS Platform Integration Audit

Phase: PCA-002

Audit date: 2026-07-15

Branch: `css-unified-consolidation-2026-07-13`

Baseline: `0320e56c2a6b79679a9c9e34aff825e44cf03c47`

Scope: repository evidence after Mission Control MC-001 through MC-007C, OP-001 operational proof documentation, and BR-001 strict broker environment profile separation. PCA-002 did not run live broker traffic, did not start or stop runtime services, and did not modify implementation code.

## Safety Boundary

PCA-002 is evidence-only. It makes no runtime, broker, execution, credential, environment, dashboard, or configuration changes.

Required posture remains:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

The audit found no evidence that advisory, paper, dashboard, Mission Control, broker readiness, certification, or Options Income modules can authorize live execution.

## Audit Method

The audit reviewed repository modules, governance docs, architecture docs, runbooks, prior operational proof evidence, route registration evidence, and test names/contracts. Repository source and executable tests take precedence over roadmap language. Where active runtime evidence is unavailable, PCA-002 classifies the area as pending active-host validation rather than assuming production-active behavior.

## Platform Inventory Summary

| Subsystem | Implementation status | Integration status | Host activation | Mission Control visibility | Dashboard/API/mobile visibility | Certification/validation status | Known limitations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Runtime and supervisor | Implemented | Integrated with dashboard, launcher, certification, broker, and Mission Control read models | Configured; active Desktop listener not proven in PCA-002 | Runtime operations, source diagnostics, freshness, state hash | Dashboard runtime contract and launcher/mobile payloads | Runtime smoke and OP-001 evidence exist | Active Desktop session proof remains separate. |
| Mission Control | Complete certified for repository scope | Integrated with web host and launcher host | Registered through `dashboard.web.web_app.create_app` and `launcher.css_mobile_launcher` | Native surface | Web and launcher routes | MC-001 through MC-007C docs/tests | Active Desktop route proof still required. |
| Dashboard web | Implemented | Integrated with runtime frontend contract and Mission Control | Configured through web app factory | Mission Control mounted | Dashboard APIs and web UI | Dashboard focused tests and RC1 docs | Provider fallback must remain explicit. |
| Mobile/launcher | Implemented | Integrated with runtime builder, Mission Control, broker, dashboard state | Configured through launcher | Mission Control mounted in launcher app | Mobile/PWA and launcher routes | Mobile/launcher tests; OP-001 noted one smoke text drift | Cross-process active host validation needed. |
| Broker layer | Implemented for advisory/read-only certification | Integrated with credential diagnostics, bootstrap, canonical broker state, profile loader | Runtime and dashboard consumers exist | Broker management/telemetry pages | Broker readiness and status payloads | Phase 153-166 and BR-001 evidence | Live broker traffic not run by PCA-002. |
| Canonical broker state | Implemented | Integrated with bootstrap, frontend contract, Mission Control | Runtime display consumer path exists | Redacted broker state visible | Dashboard/launcher broker state | BR-001 and Phase166 evidence | Secondary broker readiness builders remain drift risks. |
| Broker profiles | Implemented by BR-001 | Integrated with credential loader, bootstrap, Coinbase readiness, canonical state | Server-side loader path exists | Redacted profile metadata only | Dashboard/MC profile metadata | BR-001 tests/docs | Remaining direct env reads should be treated as migration debt. |
| Coinbase | Implemented for diagnostics/read-only readiness | Integrated with broker profiles and canonical state | Runtime readiness path exists | Broker telemetry visible | Dashboard readiness visible | Coinbase readiness/auth tests exist | Live authentication evidence is outside PCA-002. |
| OANDA | Implemented for diagnostics/read-only readiness | Integrated with broker profiles and canonical state | Runtime readiness path exists | Broker telemetry visible | Dashboard readiness visible | OANDA readiness tests/docs exist | Live quote/account proof remains separate. |
| IBKR | Partial | Inventory/adapter level only in audited evidence | Not canonical active | Not a first-class active profile | Not verified | Not certified as active | Future adapter hardening required. |
| Trading engine | Advisory/dry-run integrated | Connected to risk, decisions, dashboard summaries | Runtime read models exist | Trade operations and decision surfaces | Dashboard/mobile summaries | Execution/risk tests | Live order submission remains intentionally blocked. |
| Execution pipeline | Implemented safety gate layer | Integrated with R7, RBAC, NO-GO, firewall, risk gates | Authority path remains blocked | Safety posture displayed | Dashboard safety fields | Safety tests/docs | No approved live execution activation. |
| Decision intelligence | Implemented | Integrated with Mission Control and audit/explainability views | Read-only host surfaces exist | Decision intelligence pages | Dashboard/advisory payloads | Decision tests/docs | Multiple confidence/recommendation concepts overlap. |
| Committee framework | Implemented | Integrated with Mission Control committee projections | Display/advisory only | Committee pages and projections | Dashboard-compatible payloads | Committee tests/docs | Committee approval cannot override execution gates. |
| Portfolio | Implemented | Integrated with dashboard, Mission Control, capital/risk, OI adapters | Read-model host paths exist | Portfolio and executive pages | Dashboard/mobile summaries | Portfolio/dashboard tests | Multiple portfolio builders overlap. |
| Capital allocation | Implemented advisory/policy layer | Integrated with portfolio, order limits, risk, dashboard | Read-model host paths exist | Capital allocation and governance pages | Dashboard summaries | Capital/order-limit tests | Live limits remain restrictive and fail closed. |
| Accounting/PnL | Implemented | Integrated with dashboard/runtime reconciliation | Dashboard read path exists | Operational summaries | Runtime PnL displays | RC1-OPS remediation/docs | Active cross-process proof should be rerun. |
| Risk and AntiBleedGuard | Implemented | Integrated with execution gates, dashboard, Mission Control, OI risk | Runtime read model exists | Risk command and projections | Dashboard/mobile risk status | Risk and safety tests | Several risk calculators should retain explicit scope. |
| Options core | Implemented for models/dry-run/advisory scope | Integrated with dashboard and Options Income | Host paths via OI/dashboard | Options Income and portfolio panels | Dashboard/OI payloads | Options docs/tests | Live options broker routing not implemented. |
| Options Income | Complete for approved paper/advisory scope | Integrated with portfolio, risk, broker paper abstraction, dashboard, RC1-OI, enterprise adapters | Adapter/registration paths exist; active host proof pending | Options Income page and operations projections | OI dashboard/API payloads | OI-002 through OI-010, EI-001, RC1-OI evidence | Not live broker integrated; optional advanced strategies out of approved scope. |
| Derivatives shared services | Implemented advisory normalization | Integrated with OI RC1 integration | Library/service level | Indirect through OI/risk views | OI/dashboard projections | EI-001 evidence | Broader derivatives product platform is partial. |
| Treasury | Partial | Scattered capital/cash/buying-power concepts | No canonical host surface found | Not first-class | Not first-class | Not certified | Needs design after runtime/broker proof. |
| Audit and events | Implemented | Integrated with dashboard, runtime, OI, Mission Control evidence views | Runtime/read-model paths exist | Audit/explainability pages | Dashboard evidence hashes and event views | Audit/event tests/docs | Schemas overlap across subsystems. |
| Alerts | Implemented advisory/operational read model | Integrated with OI and Mission Control alert projections | Display paths exist | Alerts/incidents page | Dashboard/launcher summaries | Alert tests/docs | Delivery/operator workflow less mature than generation. |
| Learning and analytics | Implemented advisory engines | Integrated with portfolio, decision, Mission Control projections | Read-model paths exist | Learning/performance pages | Dashboard/advisory outputs | Learning/analytics tests | Overlapping scoring concepts require canonical fields. |
| Governance/RBAC/feature flags | Implemented | Integrated with Mission Control secure operations and dashboard visibility | Display-only host paths exist | RBAC/configuration/governance pages | Governance dashboard payloads | MC-007B and governance tests/docs | Mutation authority must remain outside dashboards. |
| Deployment/runbooks | Implemented | Integrated with release and operational proof docs | Startup command documented; active listener depends on environment | Runbook page | Operator docs | OP-001 and RC1-OPS evidence | Current active host must be proven per release. |
| Documentation | Broadly implemented | Architecture, governance, release, runbook, roadmap docs exist | Docs-only | Documentation/runbooks page | Repository docs | PCA-001, OP-001, BR-001, PCA-002 | Some legacy phase docs predate BR-001 and should be read with scope. |

## Options Income Engine Conclusion

Options Income is feature complete for the approved OI-002 through OI-010 paper/advisory scope and is enterprise-integrated through EI-001 and RC1-OI evidence.

Evidence supports:

- Paper covered-call and cash-secured-put strategy domain models.
- Opportunity scanning, lifecycle, rolling, portfolio construction, risk, Greeks, stress testing, alerts, explainability, dashboard payloads, paper broker abstraction, paper order preview, replay, audit, and certification.
- Enterprise adapters for dashboard, audit, event bus, learning, certification, runtime registration, and RC1-OI snapshots.
- Mission Control visibility through Options Income pages and portfolio/operations projections.

The engine is not live-execution capable. It is not live-broker integrated. Paper broker and preview abstractions must not be interpreted as broker execution readiness. Active Desktop host consumption of every Options Income panel remains a validation task, not an implementation blocker for the approved paper scope.

## Mission Control Conclusion

Mission Control is complete and repository-certified for its read-only institutional command-center scope.

Evidence supports:

- Host registration in dashboard web and launcher.
- Runtime snapshot provider, normalizer, source registry, active source resolver, artifact reader, endpoint reader, freshness and state hash support.
- Executive, operations, broker, portfolio, risk, decision, learning, alerts, audit, secure operations, configuration, documentation, and Options Income pages.
- GET-only/read-only posture with secret redaction and fail-closed behavior.

Mission Control is not an execution console. It displays broker and execution posture but cannot arm execution, submit orders, cancel orders, modify credentials, or change live controls. The remaining distinction is operational: active Desktop host proof must confirm the registered routes are live in the running CSS process.

## Integration Findings

1. The platform is broadly integrated by adapters and read models rather than a single monolithic runtime store.
2. BR-001 materially improved broker profile safety by removing engine-mode broker inference and adding strict profile separation.
3. Mission Control consumes existing runtime/dashboard evidence rather than creating a new execution authority.
4. Options Income is mature for paper/advisory operation and enterprise visibility, but not live broker execution.
5. The main integration risk is drift between parallel display/certification/readiness models, not accidental live execution.

## Duplication Findings

| Area | Duplicate or overlapping producers | Drift risk | Recommended owner |
| --- | --- | --- | --- |
| Runtime snapshots | Runtime artifact publisher, runtime certification snapshot, dashboard frontend contract, Mission Control normalizer | High | Canonical runtime cycle snapshot with display adapters. |
| Broker readiness | Live validation, connectivity certifier, continuous monitor, broker operational status, canonical broker state, dashboard summaries | High | Canonical broker runtime state plus scoped certificates. |
| Broker profile/environment | BR-001 profile loader plus legacy environment consumers | Medium-high | `backend/runtime/broker_environment_profiles.py`. |
| Account/balance/margin | Broker snapshots, margin adapters, dashboard state, canonical account state | High | Canonical account snapshot with provenance. |
| Dashboard payloads | Frontend contract, launcher payloads, Mission Control serializers, OI dashboard builders | Medium-high | Runtime frontend contract plus explicit subsystem adapters. |
| Portfolio summaries | Portfolio engines, analytics managers, OI portfolio, Mission Control projections | Medium | Canonical portfolio read model with contributor scopes. |
| Risk summaries | Core risk, app risk, OI risk, derivatives risk, Mission Control projections | Medium | Authoritative execution risk gates plus advisory read-model adapters. |
| Certification | RC1, broker, runtime, OI, Mission Control, operational proof certificates | Medium | Certification registry with scope and source. |
| Freshness/state hash | Runtime artifact freshness, Mission Control freshness, dashboard heartbeat, OI replay hashes | Medium | Shared freshness/hash helpers with source metadata. |
| Audit/explainability | Runtime events, dashboard evidence hashes, OI audit, Mission Control evidence graph | Medium | Canonical audit event schema. |

## Host Activation Findings

| Category | PCA-002 finding |
| --- | --- |
| Runtime active | Runtime modules and launcher integration exist. PCA-002 did not prove a currently running Desktop listener. |
| Desktop active | Configured and test-backed, but active host proof remains pending from OP-001 limitations. |
| Mobile active | Launcher and mobile modules are integrated; focused tests passed in OP-001, while standalone smoke had display text drift. |
| Mission Control active | Registered into web and launcher hosts; repository-certified. Active HTTP route proof remains pending. |
| Broker active | Readiness/certification paths exist and BR-001 profile separation is integrated. Live broker traffic was not run. |
| Options Income active | Enterprise adapters and Mission Control visibility exist. Full active-host panel proof remains pending. |
| Test-only | Paper broker scenarios, deterministic certifications, and many adapter integrations are pytest-proven. |
| Docs-only/roadmap | Treasury, swaps, advanced derivatives beyond options, and alternative data remain future scope. |

## Safety Findings

- No advisory module was found to grant live execution authority.
- Mission Control, dashboard, broker readiness, Options Income, learning, portfolio, and committee outputs remain display/advisory/read-only.
- R7, RBAC, NO-GO, execution firewall, broker startup gates, broker profiles, and live execution boundary controls remain authoritative.
- BR-001 explicitly preserves fail-closed live-read-only broker environment separation.

## Remaining Work

1. Run a controlled active Desktop host proof after BR-001.
2. Validate dashboard, mobile, Mission Control, broker, risk, capital, audit, certification, and Options Income views against one runtime snapshot.
3. Continue canonicalizing broker readiness, runtime snapshots, account/balance/margin provenance, and certification registry outputs.
4. Keep live broker validation read-only and sidecar-isolated until a separate approved pilot phase.
