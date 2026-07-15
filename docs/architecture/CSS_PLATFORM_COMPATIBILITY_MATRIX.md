# CSS Platform Compatibility Matrix

Phase: PCA-002

Audit date: 2026-07-15

Branch: `css-unified-consolidation-2026-07-13`

Baseline: `0320e56c2a6b79679a9c9e34aff825e44cf03c47`

Scope: repository evidence only after Mission Control MC-001 through MC-007C and BR-001 strict broker environment profile separation. This matrix does not certify live trading and does not change runtime behavior.

## Safety Boundary

The audited platform remains read-only, paper-only, or advisory-only unless a separate approved execution-control phase explicitly changes that posture through authoritative governance.

Required invariants:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

PCA-002 found no repository evidence that Mission Control, Options Income, broker readiness, certification, dashboard, mobile, or advisory intelligence modules grant live execution authority.

## Compatibility Classifications

| Classification | Meaning |
| --- | --- |
| `COMPATIBLE` | Contract evidence, tests, and host registration are aligned for the audited scope. |
| `COMPATIBLE_WITH_WARNINGS` | Integration exists, but duplicate producers, active-host proof gaps, or provenance risks remain. |
| `PARTIAL` | Some implementation exists, but canonical enterprise integration is incomplete. |
| `UNVERIFIED` | Repository evidence is insufficient to claim active compatibility. |
| `BLOCKED` | The pathway is intentionally disabled by governance or missing required approval. |
| `INCOMPATIBLE` | Evidence shows conflicting contracts. PCA-002 found no confirmed hard incompatibility in the audited safety paths. |

## Major Integration Matrix

| Integration | Classification | Producer | Consumer | Evidence | Compatibility notes | Required follow-up |
| --- | --- | --- | --- | --- | --- | --- |
| Runtime snapshot to Mission Control | `COMPATIBLE_WITH_WARNINGS` | Runtime snapshot provider, artifact reader, endpoint reader, source resolver | Mission Control state contract and pages | `dashboard/mission_control/runtime_snapshot_provider.py`, `runtime_snapshot_normalizer.py`, `runtime_source_resolver.py`, `host_registration.py` | MC consumes runtime-shaped state and fails closed on missing or stale evidence. Active Desktop listener proof remains separate from repository evidence. | Re-run controlled Desktop operational proof with the host active. |
| Runtime snapshot to dashboard web | `COMPATIBLE_WITH_WARNINGS` | Dashboard runtime builders and frontend contract | `dashboard.web.web_app.create_app` routes | `dashboard/web/web_app.py`, `dashboard/runtime/*` | Web app registers dashboard and Mission Control routes. Demo/provider fallback must remain explicit and non-authoritative. | Validate active provider selection in a running Desktop session. |
| Runtime snapshot to mobile/launcher | `COMPATIBLE_WITH_WARNINGS` | Launcher runtime builders | Mobile launcher routes and payloads | `launcher/css_mobile_launcher.py`, `dashboard/mobile/*` | Launcher composes runtime, broker, portfolio, Mission Control, and safety payloads. Prior OP-001 noted standalone mobile smoke text drift. | Validate mobile route display and runtime source hash in active host proof. |
| Dashboard web host to Mission Control | `COMPATIBLE` | FastAPI web host | Mission Control router | `dashboard/web/web_app.py` calls `register_mission_control` | Registration is additive and GET-only/read-only. | Keep route registration idempotent. |
| Launcher host to Mission Control | `COMPATIBLE` | Launcher FastAPI app | Mission Control router and runtime bridge | `launcher/css_mobile_launcher.py` imports `register_mission_control` and `runtime_snapshot_state_provider` | Launcher passes the same runtime-shaped state provider used by existing launcher payloads. | Keep Mission Control bound to existing launcher state, not a new store. |
| Mission Control to broker readiness | `COMPATIBLE_WITH_WARNINGS` | Canonical broker state, broker registry, redacted profile diagnostics | Mission Control broker management and telemetry pages | `dashboard/mission_control/broker_registry.py`, `broker_telemetry.py`, `backend/runtime/canonical_broker_*`, `broker_environment_profiles.py` | BR-001 adds strict profile separation and redacted profile metadata. Duplicate broker readiness/certification modules remain drift risks. | Continue making canonical broker runtime state the only displayed authority. |
| Broker environment profiles to credential loading | `COMPATIBLE` | `BrokerEnvironmentProfile` and `BrokerEnvironmentCredentials` | Credential loader, bootstrap, diagnostics | `backend/runtime/broker_environment_profiles.py`, `backend/app/brokers/credential_loader.py`, `backend/app/brokers/broker_bootstrap.py` | PAPER, LIVE_READ_ONLY, and LIVE_EXECUTION are explicit. Engine mode is not broker profile inference. | Keep direct environment reads behind profile-aware loaders. |
| Broker state to dashboard/frontend contract | `COMPATIBLE_WITH_WARNINGS` | Canonical broker state builder and adapter | Dashboard frontend contract and launcher payloads | `backend/runtime/canonical_broker_state_builder.py`, `canonical_broker_state_adapter.py`, `dashboard/runtime/frontend_contract.py`, `launcher/css_mobile_launcher.py` | BR-001 improved profile metadata and contamination reporting. Secondary display builders can still diverge. | Test all dashboard broker surfaces against canonical broker state fields. |
| Broker certification to runtime certification | `COMPATIBLE_WITH_WARNINGS` | Live broker validation, live connectivity certifier, continuous monitor, canonical runtime state | Runtime certification snapshot and dashboard display | `backend/runtime/live_broker_validation.py`, `live_connectivity_certifier.py`, `continuous_broker_health_monitor.py`, `runtime_certification_snapshot.py` | Certifications are advisory-only and read-only. Multiple certificates have different scopes and must expose provenance. | Maintain a certification index with scope, timestamp, source, and safety flags. |
| Coinbase/OANDA adapters to broker readiness | `COMPATIBLE_WITH_WARNINGS` | Broker adapters and diagnostics | Broker bootstrap, canonical state, live read-only certifiers | `backend/app/brokers/*`, `backend/runtime/*coinbase*`, `backend/runtime/*oanda*` | Read-only validations are modeled; live execution remains blocked. Live external connectivity evidence is outside PCA-002. | Run read-only broker sidecar validation under BR-001 profiles before pilot planning. |
| IBKR to broker framework | `PARTIAL` | IBKR-related broker/runtime references | Broker abstraction/readiness inventory | Repository broker directories and runtime managers | PCA-002 did not find IBKR as a canonical active broker profile equal to Coinbase/OANDA. | Treat IBKR as future adapter hardening unless later evidence promotes it. |
| Risk gates to execution pipeline | `COMPATIBLE` | R7, RBAC, NO-GO, execution firewall, risk governors | Execution pipeline and advisory surfaces | `backend/execution/*`, `backend/risk/*`, `backend/app/risk/*`, validation tests/docs | Risk gates and firewall remain authoritative. Advisory modules do not grant execution. | Preserve fail-closed gate precedence. |
| Capital policy to order previews | `COMPATIBLE_WITH_WARNINGS` | Canonical order/capital limit config | Preview builders, pilot governance, dashboard display | `tests/test_canonical_order_limit_config.py`, runtime pilot/capital modules | Existing safety tests assert dashboard/API cannot increase live limits and execution remains blocked. | Keep paper preview amounts separated from live caps. |
| Portfolio to Mission Control | `COMPATIBLE_WITH_WARNINGS` | Portfolio projections, runtime portfolio state, advisory snapshots | Mission Control portfolio and executive pages | `backend/portfolio/*`, `dashboard/mission_control/portfolio_projection.py` | Mission Control has read-only portfolio projections. Multiple portfolio builders overlap. | Define field ownership for cash, equity, exposure, and attribution. |
| Portfolio to risk and capital | `COMPATIBLE_WITH_WARNINGS` | Portfolio, allocation, and analytics engines | Risk governors, capital allocation, dashboard and Mission Control views | `backend/portfolio/*`, `backend/allocation/*`, `backend/risk/*` | Advisory optimization and risk views coexist with authoritative execution gates. | Normalize portfolio/capital/risk read models without changing gates. |
| Accounting/PnL to runtime and dashboard | `COMPATIBLE_WITH_WARNINGS` | Accounting/PnL modules | Runtime PnL, dashboard, operational proof | `backend/app/accounting/*`, dashboard runtime tests/docs | Prior runtime PnL reconciliation remediation exists. Cross-process operational validation remains important. | Use one PnL provenance path per display field. |
| Decision intelligence to Mission Control | `COMPATIBLE` | Decision traces, committee projections, opportunity ranking | Mission Control decision intelligence pages | `dashboard/mission_control/decision_intelligence.py`, `decision_trace.py`, `committee_projection.py` | Read-only decision explanation and voting display are integrated. | Preserve advisory-only labeling and veto precedence. |
| Investment committee to execution authority | `COMPATIBLE` | Committee framework and voting engine | Decision surfaces and governance reports | `backend/investment_committee/*`, `dashboard/mission_control/*committee*` | Committee decisions are governance/advisory signals only. Weighted confidence cannot override execution gates. | Keep execution authority outside committee modules. |
| Options Income to portfolio/risk | `COMPATIBLE` | OI paper portfolio, risk, Greeks, stress, allocation modules | OI dashboard, enterprise adapters, RC1-OI certification | `backend/options/options_income_*`, `backend/derivatives/*` | Complete for approved paper/advisory scope. | Keep paper-only scope explicit. |
| Options Income to broker abstraction | `COMPATIBLE` | OI paper broker abstraction | OI certification, dashboard, paper preview | `backend/options/options_income_*broker*`, OI-009 docs/tests | Paper broker and preview layers do not connect to live broker execution. | Do not treat paper broker readiness as live broker readiness. |
| Options Income to Mission Control | `COMPATIBLE_WITH_WARNINGS` | OI enterprise/dashboard/certification adapters | Mission Control Options Income and operations projections | `backend/options/options_income_*adapter.py`, `dashboard/mission_control/pages/options_income.py`, `portfolio_projection.py` | Repository adapters exist and are test-backed. Active host consumption of every OI panel still requires operational proof. | Validate OI panels in a running Desktop host. |
| Shared derivatives to Options Income | `COMPATIBLE` | Shared derivatives exposure, stress, volatility services | OI RC1 integration | `backend/derivatives/*`, `backend/options/options_income_rc1_integration.py` | Shared services are read-only normalization helpers. | Reuse shared services before adding new derivatives views. |
| Treasury/cash-liquidity to platform | `PARTIAL` | Capital, portfolio, buying-power concepts | Dashboard/portfolio/capital views | `backend/allocation/*`, `backend/portfolio/*`, risk/capital modules | No canonical treasury workflow, liquidity ladder, cash operations, or swap product host surface was found. | Defer treasury implementation until runtime/broker proof is complete. |
| Audit/events to runtime and dashboard | `COMPATIBLE_WITH_WARNINGS` | Event normalization, evidence hashing, audit adapters | Runtime, dashboard, Mission Control, OI integration | `backend/events/*`, `dashboard/runtime/evidence_hashing.py`, OI audit/event adapters | Audit data is read-only, but subsystem-specific schemas overlap. | Normalize audit event schema with source scope and evidence hash. |
| Alerts to Mission Control and dashboard | `COMPATIBLE_WITH_WARNINGS` | Monitoring and OI alert builders | Dashboard, launcher, Mission Control alert pages | `backend/monitoring/*`, `backend/options/options_income_alerts.py`, `dashboard/mission_control/alerts_incidents.py` | Alert generation exists; delivery/operator workflow evidence is less mature. | Preserve display-only alert actions until workflow authority is specified. |
| Learning/analytics to advisory outputs | `COMPATIBLE_WITH_WARNINGS` | Learning engines, analytics, adaptive strategy modules | Portfolio, Mission Control, dashboard projections | `backend/learning/*`, `backend/analytics/*`, `backend/portfolio/*` | Recommendations are advisory. Strategy/confidence concepts overlap across packages. | Standardize recommendation score/provenance fields. |
| Governance/RBAC/feature flags to Mission Control | `COMPATIBLE` | Governance, security, feature-flag modules | Mission Control secure operations and configuration pages | `dashboard/mission_control/rbac_console.py`, `feature_flags.py`, `permissions.py`, governance docs | Mission Control displays controls without write-capable live mutation routes. | Keep secure operations surfaces read-only. |
| Deployment/runbooks to runtime architecture | `COMPATIBLE_WITH_WARNINGS` | Launcher, scripts, runbooks, release docs | Operators and validation workflows | `launcher/*`, `docs/runbooks/*`, `docs/release/*`, operations docs | Startup paths exist, but active host status is runtime-environment dependent. | Keep canonical startup command documented and test current Desktop session. |

## No Confirmed Hard Incompatibilities

PCA-002 found no confirmed incompatible authority path in the audited repository evidence. The material risks are compatibility warnings caused by duplicate read models, multiple certification scopes, and active-host validation gaps.

## Compatibility Priorities

1. Prove active Desktop host state with Mission Control, dashboard, mobile, broker, Options Income, risk, capital, audit, and certification views in one read-only runtime session.
2. Treat BR-001 broker environment profiles as the canonical source for broker profile selection and contamination evidence.
3. Keep canonical broker runtime state and runtime certification snapshots as display authorities.
4. Consolidate duplicated portfolio, risk, capital, dashboard, freshness, and certification read models.
5. Preserve advisory-only and fail-closed safety flags in every surface.
