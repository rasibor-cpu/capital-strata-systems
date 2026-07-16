# CSS Platform Duplication And Consolidation Register

Phase: PCA-001

Baseline SHA: 502fb70587b0597873a7a2531589cc6d75261220

| Area | Modules Involved | Canonical Implementation | Legacy / Parallel Implementation | Risk Of Divergence | Recommended Consolidation | Urgency | Migration Complexity |
|---|---|---|---|---|---|---|---|
| Broker readiness/status | backend/runtime/canonical_broker_state_builder.py; backend/runtime/coinbase_readiness.py; backend/runtime/oanda_readiness.py; dashboard/mission_control/state_adapter.py | canonical_broker_state_builder | Readiness-specific adapters and frontend reshaping layers | High | Make canonical broker runtime state the only status authority; adapters become pure projections | High | Medium |
| Runtime snapshot generation | backend/runtime/runtime_certification_snapshot.py; dashboard/mission_control/runtime_snapshot_provider.py; dashboard/mission_control/runtime_source_resolver.py | runtime_certification_snapshot plus source_resolver | Multiple state wrapping layers | High | Define one canonical snapshot envelope with versioned adapters only | High | Medium |
| Freshness logic | dashboard/mission_control/freshness.py; runtime artifact freshness modules | mission_control freshness summaries | Multiple freshness derivations in runtime/dashboard | Medium | Reuse a single freshness evaluator across consumers | Medium | Low |
| State hashing | dashboard/mission_control/serializers.py; canonical broker/runtime state builders | canonical broker/runtime stable hash | Per-surface state hashing | Medium | Standardize one hash contract for runtime and derived views | Medium | Medium |
| Safety flags propagation | Many runtime, dashboard, certification payload builders | canonical safe flags in broker/runtime state | Repeated inline fields in many payloads | Medium | Centralize safe flag mixin/helper | Medium | Low |
| Environment loaders | backend/runtime/broker_environment_profiles.py; backend/runtime/live_environment_loader.py | broker_environment_profiles.build_broker_environment | startup wrappers and legacy loader paths | High | Keep one canonical profile loader and reduce wrapper logic | High | Medium |
| Credential aliases | broker env profile and readiness modules | profile-scoped credential abstraction | many legacy alias env names | High | Publish deprecation path and reduce alias set | High | Medium |
| Dashboard payload projections | dashboard/runtime/frontend_contract.py; dashboard/mission_control/state_adapter.py | frontend_contract | mission-control-specific projection reshaping | Medium | Minimize bespoke projection logic in Mission Control | Medium | Medium |
| Options Income runtime integration | options_income_runtime_registration.py; options_income_rc1_runtime_snapshot.py | RC1 runtime registration/snapshot | test-only host registries and panel stubs | Medium | Promote runtime registration into canonical host path | High | Medium |
| Alerts/explainability/report shapes | backend/notifications/*; backend/options/options_income_* adapters | domain payload builders | parallel report/evidence wrappers | Medium | Normalize envelope schema across subsystems | Medium | Medium |
| Certification reporting | RC1 platform docs, OI docs, mission control docs | release-level certification summary | subsystem-specific certification reports | Low | Keep hierarchy but share common evidence schema | Low | Medium |
| Legacy script patchers | scripts/build_* and root patch scripts | canonical runtime/host code paths | legacy repository mutation scripts | High | Mark deprecated and move to archive/quarantine | High | Low |

## Priority Consolidation Themes

1. Broker and runtime state authority consolidation.
2. Environment loader and credential alias simplification.
3. Mission Control/frontend contract projection deduplication.
4. Canonical host activation for Options Income enterprise services.

## Migration Guidance

1. Prefer adapter slimming over broad refactors.
2. Preserve fail-closed posture while reducing duplication.
3. Quarantine placeholder and legacy patch scripts before enabling broader operational hosts.
