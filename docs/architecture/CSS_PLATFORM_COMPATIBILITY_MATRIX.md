# CSS Platform Compatibility Matrix

Phase: PCA-001

Baseline: `584c6a28c38d792312c0edaf07533ca933d24266`

This matrix classifies major service and contract relationships as `COMPATIBLE`, `COMPATIBLE_WITH_WARNINGS`, `INCOMPATIBLE`, or `UNVERIFIED`.

| Integration | Classification | Producer | Consumer | Evidence | Compatibility notes | Recommended action |
| --- | --- | --- | --- | --- | --- | --- |
| Runtime snapshot to Mission Control | `COMPATIBLE` | Runtime snapshot provider, normalizer, source resolver | Mission Control routes and state adapter | `dashboard/mission_control/runtime_snapshot_provider.py`, `runtime_snapshot_normalizer.py`, `host_registration.py` | Mission Control supports fail-closed unavailable/stale states and source hashes. | Validate in active Desktop host. |
| Runtime snapshot to mobile dashboard | `COMPATIBLE_WITH_WARNINGS` | Launcher runtime builders and dashboard frontend contract | Mobile/launcher UI | `launcher/css_mobile_launcher.py`, `dashboard/runtime/frontend_contract.py` | Cross-process freshness and artifact availability are runtime-sensitive. | Include in Desktop operational proof. |
| Frontend contract to dashboard web host | `COMPATIBLE` | Dashboard hydration/frontend contract | `dashboard.web.web_app.create_app` | `dashboard/web/web_app.py`, `dashboard/runtime/*` | Web host registers state and websocket routers. Demo provider is intentionally used only when no injected provider exists. | Ensure production launch injects canonical provider. |
| Dashboard web host to Mission Control | `COMPATIBLE` | Web host FastAPI app | Mission Control host registration | `dashboard/web/web_app.py` calls `register_mission_control`. | Registration is additive and read-only. | Keep route registration idempotent. |
| Launcher host to Mission Control | `COMPATIBLE` | Launcher FastAPI app | Mission Control host registration | `launcher/css_mobile_launcher.py` imports `register_mission_control` and runtime bridge. | Launcher provides active runtime-shaped state. | Validate startup route availability. |
| Canonical broker state to broker diagnostics | `COMPATIBLE_WITH_WARNINGS` | Canonical broker state/certification modules | Diagnostics, readiness, dashboard, runtime | `backend/runtime/canonical_broker_*`, `backend/runtime/broker_credential_diagnostics.py` | Multiple readiness and diagnostic modules exist; canonical state must remain authoritative. | Prohibit secondary health calculations from overriding canonical result. |
| Canonical broker state to margin and capital | `COMPATIBLE_WITH_WARNINGS` | Broker account snapshots/margin adapters | Margin dashboard and capital views | `engine/risk/*margin_adapter.py`, runtime account snapshot modules | Prior readiness phases show account/balance/buying-power ambiguity can occur if provenance is not explicit. | Preserve provenance and fail-closed missing fields. |
| Broker capability models to runtime readiness | `COMPATIBLE_WITH_WARNINGS` | Broker capability/certifier modules | Runtime readiness and dashboard surfaces | `backend/runtime/live_connectivity_certifier.py`, broker capability modules | Capability information should be cached per cycle and not recomputed per dashboard refresh. | Consume canonical certifier output. |
| Risk state to trade gate | `COMPATIBLE` | Risk governors and limits | Execution gates | `backend/risk/*`, `engine/risk/*`, execution tests | Risk gates fail closed and do not grant authority. | Preserve R7/RBAC/NO-GO authority. |
| Capital state to execution boundary | `COMPATIBLE` | Capital and pilot-limit config | Execution boundary validation | Capital/order-limit tests and live pilot governor | Limits default safely and dashboards cannot increase live limits. | Keep typed config canonical. |
| Decision intelligence to audit evidence | `COMPATIBLE_WITH_WARNINGS` | Decision traces, explanations, evidence graph | Audit/event surfaces and Mission Control | `dashboard/mission_control/decision_trace.py`, `evidence_graph.py`, audit modules | Multiple explanation/evidence views can drift. | Align fields to canonical audit event schema. |
| Portfolio state to accounting | `COMPATIBLE_WITH_WARNINGS` | Portfolio state builders | Accounting/PnL/dashboard projections | `backend/portfolio/*`, accounting modules | Multiple portfolio/accounting projections exist. | Select authoritative source per field. |
| Portfolio state to risk | `COMPATIBLE_WITH_WARNINGS` | Portfolio projections | Risk governors/stress/concentration | Portfolio and risk modules | Strong coverage, but duplicated risk calculations across domains. | Consolidate read-model calculations. |
| Options Income to portfolio | `COMPATIBLE` | OI portfolio construction | OI dashboard and enterprise adapters | OI-006 modules/tests | Paper/advisory portfolio construction is complete for approved scope. | Keep paper-only labeling. |
| Options Income to risk | `COMPATIBLE` | OI risk governance | OI dashboard, RC1-OI integration | OI-007 modules/tests | Risk limits are advisory/paper-only. | Do not mix with live execution gates. |
| Options Income to Mission Control | `COMPATIBLE_WITH_WARNINGS` | OI enterprise/dashboard adapters | Mission Control operations/intelligence projections | OI RC1 integration and Mission Control modules | Adapter evidence exists; continuous runtime host consumption was not PCA-verified. | Run active host proof. |
| Shared derivatives to Options Income | `COMPATIBLE` | Shared derivatives exposure/stress/volatility services | OI RC1 integration | `backend/derivatives/*`, `backend/options/options_income_rc1_integration.py` | Read-only normalization is compatible. | Reuse before creating new derivatives services. |
| Options broker abstraction to live broker subsystem | `UNVERIFIED` | OI paper broker abstraction | Live broker adapters | OI-009 modules/tests | OI broker abstraction is paper-only and does not register live brokers. | Treat live broker integration as future scope. |
| Certification to RC1 readiness | `COMPATIBLE_WITH_WARNINGS` | Certification modules | Runtime, dashboard, governance docs | RC1 and phase certification docs/tests | Multiple certificates exist for different scopes. | Expose scope and provenance in every certificate. |
| Feature flags to safety gates | `COMPATIBLE_WITH_WARNINGS` | Feature flag/configuration modules | Runtime/dashboard/governance surfaces | Governance and Mission Control secure ops modules | Visibility exists; mutation paths must remain controlled. | Keep dashboards read-only for live controls. |
| RBAC to operator permissions | `COMPATIBLE` | RBAC/security modules | Mission Control secure operations | MC-007B modules/tests | Mission Control displays permission state without write-capable control routes. | Preserve GET-only posture. |
| Runtime artifacts to source resolver | `COMPATIBLE` | Runtime artifact publisher/files | Mission Control source resolver/readers | Mission Control runtime artifact reader/endpoint reader/source diagnostics | Supports fail-closed stale/missing evidence. | Continue hash/freshness validation. |
| Deployment scripts to current runtime architecture | `COMPATIBLE_WITH_WARNINGS` | Launcher/scripts/runbooks | Desktop/web/mobile hosts | `scripts/*`, `launcher/*`, `docs/runbooks/*` | Startup paths exist; Python invocation differences can confuse validation. | Standardize documented commands and venv usage. |
| Treasury roadmap to current platform | `UNVERIFIED` | Roadmap/governance fragments | Enterprise runtime/dashboard | Scattered capital/portfolio code | No canonical treasury host surface was verified. | Defer until runtime/broker proof is stable. |
| Live execution authority to advisory modules | `COMPATIBLE` | Execution firewall/R7/RBAC/NO-GO | Advisory modules | Safety tests and module boundaries | Advisory modules do not grant authority. | Keep this invariant as a release blocker. |

## Incompatibilities

PCA-001 found no repository evidence that an advisory module directly grants live execution authority. The main compatibility risks are warnings rather than confirmed incompatibilities:

- Duplicate status and certification surfaces can diverge.
- Some implemented adapters are not proven as active host consumers.
- Prior environment loading and broker authentication issues make current live read-only evidence necessary before any pilot planning.
- Deployment/runbook evidence must be refreshed against the active Desktop runtime.
