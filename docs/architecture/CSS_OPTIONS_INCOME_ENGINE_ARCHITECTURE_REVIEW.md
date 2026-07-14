# CSS Options Income Engine Architecture Integration Review

Date: 2026-07-14

Branch: `css-unified-consolidation-2026-07-13`

Phase: OI-011A

Classification: Analysis / Governance Only

## Executive Summary

The Options Income Engine from OI-001 through OI-010 is architecturally sound as a paper-only, advisory subsystem. It has strong internal modularity, deterministic tests, fail-closed behavior, and repeated safety flags across portfolio, risk, dashboard, broker abstraction, runtime validation, replay validation, audit reporting, and certification reporting.

The engine is not yet an enterprise-integrated production subsystem. Its most important design tradeoff is intentional local duplication: OI-006 through OI-010 created options-specific portfolio construction, risk budgets, dashboard payloads, alerts, explainability, paper broker abstraction, certification, replay, and audit reporting so the options-income roadmap could progress without weakening live trading controls.

That tradeoff is appropriate for controlled paper certification. For institutional production readiness, the next architectural work should consolidate read-only outputs into existing CSS platform services rather than expanding separate options-specific authorities.

Overall architectural score: 82 / 100.

Institutional readiness assessment: ready for controlled paper and read-only certification; not ready for live options execution or production runtime activation.

## Current Architecture

The current Options Income Engine is concentrated under `backend/options` with governance and completion evidence under `docs/governance` and `docs/architecture`.

Primary OI capabilities reviewed:

| Phase | Capability | Current architectural role |
| --- | --- | --- |
| OI-001 | Foundation | Uses existing canonical options, Greeks, dry-run lifecycle, dashboard metadata, and options governance foundations. |
| OI-002 | Strategy domain | Paper-safe covered-call and cash-secured-put domain model. |
| OI-003 | Opportunity scanner | Deterministic income opportunity ranking and acceptance/rejection. |
| OI-004 | Paper lifecycle | Paper short-premium position lifecycle, collateral, premium accounting, expiration, and assignment simulation. |
| OI-005 | Position management | Paper position health, income metrics, and advisory rolling recommendations. |
| OI-006 | Portfolio construction | Paper income allocation, constraints, diversification, laddering, targets, and rebalance advice. |
| OI-007 | Risk and Greeks governance | Paper Greeks aggregation, risk budgets, limits, assignment risk, volatility risk, and stress testing. |
| OI-008 | Dashboard and operational intelligence | Paper-only read models, API payload helpers, alerts, explainability, and operational status. |
| OI-009 | Broker abstraction | Paper options providers, market data snapshots, broker registry, capabilities, health, and order preview. |
| OI-010 | Controlled paper certification | End-to-end validation, replay validation, runtime safety validation, readiness scoring, audit report, and certification report. |

The subsystem consistently preserves:

- `advisory_only=true`
- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- paper-only certification scope

## CSS Systems Reviewed

The review compared OI-001 through OI-010 against the following CSS subsystems:

- Trading orchestration: `backend/execution/unified_execution_pipeline.py`, cross-asset execution adapters, dry-run options lifecycle.
- Strategy orchestration: existing options strategy engines, trade decision orchestration, adaptive strategy intelligence.
- Portfolio engine: `backend/portfolio/*`, capital rotation, portfolio decision orchestration, institutional portfolio optimizer.
- Capital allocation: app-level capital allocation governors and OI-specific allocation modules.
- Risk governance: portfolio risk governors, app risk gates, OI-specific risk budgets and stress testing.
- Runtime supervisor: runtime certification snapshot, operational proving, live readiness state machines.
- Operational intelligence: OI operational intelligence, dashboard service, operational command centre.
- Event bus: `backend/events/*`, runtime event normalization, visibility layer.
- Dashboard architecture: dashboard service, runtime frontend contract, web/mobile display surfaces.
- API architecture: read-only OI route helpers and enterprise dashboard services.
- Paper trading framework: unified paper-safe execution and OI paper lifecycle.
- Broker abstraction: global broker registry/readiness/diagnostics and OI paper broker abstraction.
- Broker diagnostics: Phase 153-156 broker readiness, credentials, connectivity, and health monitors.
- Certification framework: enterprise certification engine, RC1 readiness, runtime certification snapshot, OI-010 certification.
- Production readiness framework: RC1 readiness and operational proving.
- Governance documentation: OI roadmap, OI completion matrix, Phase OI-002 through OI-010 docs.
- Release certification: RC1 readiness and broker/runtime certification.
- Observability and health monitoring: CSS alert service, health metrics, runtime health aggregation, OI broker health.
- Audit trail: institutional audit intelligence, event stores, OI audit report.
- Explainability: enterprise explainability and OI-specific explainability.
- Learning framework: adaptive strategy intelligence, strategy effectiveness tracking, regime mapping.
- Institutional optimization: portfolio optimization, allocation, decision validation.
- Execution pipeline: unified execution pipeline and dry-run options adapter.

## Strengths

1. Safety posture is clear and repeated.

OI modules consistently include advisory-only and execution-blocking flags. The paper broker abstraction rejects live mode, the dashboard builder validates safe posture, and OI-010 runtime validation recursively checks unsafe payloads.

2. Modular decomposition is strong.

Strategy domain, scanner, lifecycle, rolling, portfolio, Greeks, risk, dashboard, broker abstraction, replay, audit, and certification are separated into focused modules. This makes future consolidation possible without a large rewrite.

3. Deterministic paper certification is valuable.

OI-010 creates a stable, replayable certification scenario with fixed timestamps and stable JSON hashing. This is a good pattern for regression and future release evidence.

4. Fail-closed behavior is deliberate.

Malformed portfolios, missing Greeks, unsafe dashboard posture, live broker mode, duplicate certification reports, replay drift, and missing audit evidence fail closed rather than infer readiness.

5. Broker safety is preserved.

OI-009 is a paper broker abstraction. It does not register live brokers, call live broker APIs, submit orders, cancel orders, mutate broker state, or arm execution.

6. Documentation is better than average for a subsystem at this stage.

The OI roadmap, completion matrix, phase docs, and OI-010 certification doc give a clear record of what exists and what remains out of scope.

## Weaknesses

1. Integration is mostly local to `backend/options`.

The engine produces good paper outputs but does not yet register those outputs with enterprise runtime supervision, canonical event streams, enterprise dashboard snapshots, or RC1 certification.

2. Several services duplicate enterprise patterns.

OI local modules repeat platform concepts for portfolio construction, risk budgets, alerts, explainability, broker health, audit reporting, replay validation, and certification readiness.

3. Dashboard/API surfaces are read-model helpers, not host-integrated views.

OI-008 creates deterministic payloads and route helpers, but broader dashboard/runtime consumers do not yet use a canonical options income snapshot.

4. Paper broker abstraction is separate from the global broker layer.

This is safe, but it means capability reporting and health scoring can diverge unless normalized before production use.

5. Greeks and stress testing are options-specific rather than derivatives-wide.

The OI Greeks aggregator and stress engine are useful, but there is also a broader derivatives and trading Greeks foundation. A shared derivatives risk service would reduce repeated exposure logic.

6. Certification is not yet part of RC1 readiness.

OI-010 certifies paper behavior, while enterprise certification and RC1 readiness live elsewhere. That separation is acceptable now but should not persist into production readiness.

7. Audit and replay are not platform-wide.

OI replay and audit report builders are deterministic but separate from event persistence, evidence hashing, and institutional audit intelligence.

## Duplication Identified

| OI capability | Existing CSS capability | Duplication type | Assessment |
| --- | --- | --- | --- |
| OI-006 portfolio construction | `backend/portfolio/*` and capital allocation governors | Portfolio allocation logic | Preserve locally for paper certification, then expose as an input to enterprise portfolio decisions. |
| OI-007 risk budgets and limits | app risk governors, portfolio risk committee, risk policy modules | Risk governance pattern | Merge policy representation later; do not merge until options collateral semantics are stable. |
| OI-007 Greeks aggregation | `backend/trading/greeks_engine.py`, portfolio Greeks tests | Derivatives exposure aggregation | Promote to shared derivatives risk service. |
| OI-007 stress testing | portfolio resilience/scenario engines | Stress scenario pattern | Convert options stress scenarios into shared portfolio stress inputs. |
| OI-008 dashboard payloads | dashboard service and frontend contract | Read-model generation | Move toward one canonical runtime snapshot consumed by all dashboards. |
| OI-008 alerts | `backend/monitoring/css_alert_service.py` | Alert emission/storage | Reuse enterprise alert service for runtime alerts; keep local alert builder as pure classifier. |
| OI-008 explainability | `backend/intelligence/explainability.py`, portfolio explainability | Explanation generation | Introduce shared explainability schema and route OI explanations through it. |
| OI-009 broker registry/health | global broker registry, diagnostics, runtime certification snapshot | Broker capability and health reporting | Keep paper provider local, but register capabilities through global broker metadata before production. |
| OI-010 certification/readiness | enterprise certification, RC1 readiness, runtime certification snapshot | Certification scoring and reporting | Integrate OI evidence into enterprise certification as a domain section. |
| OI-010 replay validation | event replay and evidence hashing | Deterministic replay | Promote stable replay harness pattern to platform-wide certification. |
| OI-010 audit report | institutional audit intelligence | Audit packaging | Feed OI audit records into enterprise audit categories. |

## Specific Question Findings

1. Does Options Income duplicate any existing CSS capability?

Yes, intentionally. The largest overlaps are portfolio construction, risk governance, dashboard payloads, alerts, explainability, broker capability/health, replay, audit, and certification. The duplication is acceptable for paper isolation but should not become a second production authority stack.

2. Should portfolio construction become part of the enterprise portfolio engine?

Yes, eventually. OI-006 should become a domain-specific portfolio construction provider that emits candidates, constraints, collateral utilization, and income targets into the enterprise portfolio engine. The enterprise portfolio engine should remain the cross-asset portfolio authority.

3. Should Greeks aggregation become a shared derivatives service?

Yes. OI-007 Greeks aggregation should be promoted into a shared derivatives exposure service covering options income, directional options, spreads, futures, and portfolio Greeks.

4. Should broker abstraction move into the global broker layer?

Partially. The OI paper broker provider should remain paper-only. Its capability and health metadata should be normalized into the global broker framework so readiness dashboards do not need separate options-specific broker logic.

5. Should dashboard payloads be unified?

Yes. OI-008 should eventually emit an options income section into a canonical runtime/dashboard snapshot consumed by desktop, mobile, runtime API, and launcher dashboards.

6. Should risk budgets merge into institutional risk governance?

Yes, but only after preserving options-specific collateral, assignment, expiry, short-premium, IV, vega, and stress semantics. Enterprise risk governance should own final cross-asset risk state.

7. Should certification integrate with RC1 certification?

Yes. OI-010 should become a read-only domain evidence section in enterprise certification and RC1 readiness. It must remain advisory and must not imply live options authority.

8. Should alerts reuse enterprise alerting?

Yes. OI alert generation should remain a pure classifier, while persistence, routing, severity normalization, and dashboard display should use enterprise alerting.

9. Should explainability become a shared subsystem?

Yes. OI explainability should use a shared evidence-backed explanation schema so strategy, risk, portfolio, and dashboard explanations are consistent across CSS.

10. Should replay validation become platform-wide?

Yes. OI-010's deterministic replay and stable JSON hashing are strong enough to become a platform certification pattern.

11. Should paper broker become part of the canonical broker framework?

Partially. Paper options providers should register as paper-only capability providers, not as live brokers. This gives observability and capability consistency without creating execution authority.

12. Should Options Income register with runtime supervision?

Yes, as a read-only supervised paper subsystem with health, data freshness, certification, and advisory state. It must not register as an executable runtime actor.

13. Should operational readiness merge into enterprise readiness?

Yes. OI readiness dimensions should feed enterprise readiness as a domain-level signal, not a separate release authority.

14. Should audit reporting merge into enterprise audit?

Yes. OI audit records should flow into institutional audit intelligence and persistent evidence stores.

15. Should stress testing become platform-wide?

Yes. Options stress scenarios should become derivatives stress inputs to the enterprise portfolio resilience and scenario framework.

## Reuse Opportunities

| Priority | Reuse opportunity | Target CSS service |
| --- | --- | --- |
| High | Publish OI-010 certification as enterprise certification evidence | `backend/certification/*`, `backend/validation/rc1_readiness.py` |
| High | Register OI dashboard output into canonical dashboard snapshots | `backend/dashboard/*`, dashboard runtime frontend contract |
| High | Feed OI lifecycle and certification events into event bus and audit | `backend/events/*`, `backend/operations/audit_intelligence.py` |
| High | Normalize OI paper broker capability and health | global broker registry/readiness/diagnostics |
| Medium | Promote Greeks aggregation to derivatives risk service | `backend/trading/greeks_engine.py`, portfolio Greeks aggregation |
| Medium | Map OI risk budgets to enterprise risk policy | `backend/risk/*`, `backend/app/risk/*`, portfolio risk committee |
| Medium | Route OI alert classifications through enterprise alerting | `backend/monitoring/css_alert_service.py` |
| Medium | Add OI decisions to learning and strategy effectiveness tracking | `backend/learning/*` |
| Low | Generalize OI replay validator into platform certification replay | `backend/events/event_replay.py`, evidence hashing |

## Recommended Consolidations

1. Certification consolidation

Make OI-010 a domain evidence provider for enterprise certification. The enterprise certifier should aggregate OI status, replay status, audit status, and readiness score without recalculating them.

2. Dashboard consolidation

Create one canonical options income runtime snapshot for all display surfaces. OI-008 should generate the domain payload, while dashboard services should own distribution and host contracts.

3. Broker capability consolidation

Represent the OI paper broker as a paper-only capability provider in global broker metadata. Live broker support should remain absent until a separate certified phase.

4. Risk and Greeks consolidation

Promote OI Greeks, assignment exposure, IV exposure, and stress scenarios into shared derivatives risk primitives. Keep options-income policy thresholds as configuration.

5. Event/audit consolidation

Emit normalized OI opportunity, lifecycle, roll, risk, dashboard, and certification events into the enterprise event bus and audit intelligence. These events must be append-only and non-authoritative.

6. Alert/explainability consolidation

Use enterprise alert persistence/routing and shared explainability schema while preserving OI's domain-specific alert and explanation classifications.

## Recommended Shared Services

| Shared service | Purpose | OI modules that should consume or expose it |
| --- | --- | --- |
| Options income runtime snapshot | Canonical read-only payload for dashboard/runtime/API | OI-008, OI-010 |
| Derivatives exposure service | Shared Greeks, expiry, IV, assignment, and stress primitives | OI-007, trading Greeks, portfolio Greeks |
| Enterprise certification adapter | Domain evidence ingestion for RC1/certification | OI-010 |
| Paper broker capability registry | Paper-only provider metadata and health normalization | OI-009 |
| Event/audit evidence adapter | Stable event taxonomy and audit trail writes | OI-004 through OI-010 |
| Enterprise alert bridge | Alert persistence, routing, severity normalization | OI-008 |
| Shared explainability schema | Evidence-backed explanation contracts | OI-008, portfolio, intelligence |
| Learning feedback adapter | Strategy effectiveness and regime learning from paper outcomes | OI-003 through OI-005 |

## Recommended Refactoring

No refactoring is recommended inside Phase OI-011A. Future phases should use additive adapters first, then retire duplication only after tests prove parity.

Recommended sequence:

1. Add adapter interfaces that expose OI outputs to platform services without changing OI internals.
2. Add contract tests proving dashboard, certification, event, and audit payload compatibility.
3. Move canonical shared logic only after an adapter has stable tests and consumers.
4. Preserve OI paper-only flags through all shared service boundaries.
5. Keep live options execution blocked until a separate approved production certification phase.

## Recommended Future Roadmap

| Priority | Phase candidate | Objective | Safety boundary |
| --- | --- | --- | --- |
| P0 | OI-011B | Add OI architecture integration adapters for certification, events, audit, and dashboard snapshots | Read-only, paper-only |
| P0 | OI-011C | Add regression tests proving shared snapshot and enterprise certification consistency | No runtime behavior change |
| P1 | OI-012 | Register Options Income as a supervised paper subsystem | Not executable |
| P1 | OI-013 | Promote Greeks and stress primitives into shared derivatives risk service | Advisory only |
| P1 | OI-014 | Integrate OI audit evidence with institutional audit intelligence | Append-only |
| P2 | OI-015 | Integrate OI paper outcomes with adaptive strategy learning | Advisory recommendations only |
| P2 | OI-016 | Normalize paper broker capability metadata with global broker diagnostics | No live broker calls |
| P3 | OI-017 | Build production certification package for read-only options data sourcing | Certification only |
| P4 | Future | Consider live options integration only after separate broker authority, assignment, approval-level, and execution-gate certification | Explicit approval required |

## Technical Debt

- OI dashboard payloads are not yet consumed by enterprise dashboard runtime contracts.
- OI certification is not yet a section in enterprise certification or RC1 readiness.
- OI event taxonomy is not registered in the enterprise event bus.
- OI audit reports do not feed institutional audit intelligence.
- OI paper broker capability and health are separate from global broker health.
- OI risk budgets are local rather than enterprise policy objects.
- OI stress scenarios and Greeks aggregation are not shared derivatives services.
- OI paper outcomes do not feed learning/regime effectiveness modules.
- OI route helpers are not host-integrated API endpoints.

## Production Concerns

The engine is not production-ready for live trading. Production blockers include:

- no live options broker adapter
- no broker-sourced option-chain authority
- no live account option approval-level validation
- no broker-state authority for options positions, collateral, assignment, or buying power
- no assignment/exercise execution workflow
- no roll order execution workflow
- no multi-leg order routing
- no production runtime supervision
- no enterprise certification integration
- no evidence/journal/event integration

These are not current defects. They are deliberate out-of-scope boundaries for the paper-only roadmap.

## Certification Concerns

OI-010 certifies deterministic paper behavior only. It should not be interpreted as:

- approval for live options trading
- approval for broker order routing
- approval for assignment or exercise instructions
- approval for live option-chain ingestion
- enterprise RC1 certification
- replacement for R7/RBAC/NO-GO/firewall controls

The future certification architecture should make OI-010 a domain-level evidence input to enterprise certification.

## Deployment Concerns

Current deployment posture should remain:

- no live options deployment
- no broker adapter changes
- no live credential use
- no runtime execution registration
- no dashboard action buttons for OI execution
- no route that mutates broker state
- no automatic capital allocation

Read-only deployment of OI dashboard/certification payloads is reasonable after OI output is normalized into enterprise dashboard and runtime supervision contracts.

## Priority Matrix

| Item | Impact | Risk if delayed | Implementation risk | Priority |
| --- | --- | --- | --- | --- |
| Enterprise certification integration | High | Parallel readiness states diverge | Low | P0 |
| Runtime/dashboard snapshot unification | High | Dashboard/API inconsistency | Medium | P0 |
| Event and audit integration | High | Weak institutional traceability | Medium | P0 |
| Paper broker capability normalization | Medium | Broker health ambiguity | Low | P1 |
| Shared derivatives Greeks service | Medium | Duplicated exposure logic | Medium | P1 |
| Enterprise risk policy mapping | High | Cross-asset risk inconsistency | Medium | P1 |
| Enterprise alert integration | Medium | Duplicate alert surfaces | Low | P2 |
| Shared explainability schema | Medium | Explanation fragmentation | Medium | P2 |
| Learning feedback adapter | Medium | Missed paper outcome intelligence | Medium | P2 |
| Live options broker integration | Very High | Cannot support live options | Very High | Future only |

## Risk Assessment

| Risk | Current level | Rationale | Recommended control |
| --- | --- | --- | --- |
| Execution authority leakage | Low | OI modules are paper-only and repeatedly block execution. | Continue safety flag contract tests. |
| Divergent dashboard state | Medium | OI dashboard payload is local and not canonical runtime state. | Add canonical snapshot adapter. |
| Divergent certification state | Medium | OI certification and enterprise certification are separate. | Add enterprise certification section. |
| Duplicated risk authority | Medium | OI risk budgets could conflict with enterprise risk if activated directly. | Map OI risk to enterprise policy before runtime activation. |
| Broker capability confusion | Medium | OI paper broker has its own registry/health. | Normalize as paper-only capability provider. |
| Audit incompleteness | Medium | OI audit is report-based, not event-backed. | Add event/audit bridge. |
| Production misuse of paper certification | Medium | OI-010 is strong enough to be misread as production approval. | Keep docs and payloads explicit: paper-only, not live. |
| Live options operational risk | High | Broker state, assignment, approval level, and live chain authority are absent. | Separate future certification phase only. |

## Institutional Readiness Assessment

| Area | Readiness | Finding |
| --- | --- | --- |
| Controlled paper strategy evaluation | Ready | OI-002 through OI-005 are deterministic and test-covered. |
| Paper portfolio and risk governance | Ready for paper | OI-006 and OI-007 provide strong local paper governance. |
| Read-only dashboard payloads | Ready for integration | OI-008 payloads are safe but not host-canonical. |
| Paper broker abstraction | Ready for paper | OI-009 is safe and broker-neutral but separate from global broker metadata. |
| Controlled paper certification | Ready | OI-010 provides deterministic certification and replay evidence. |
| Enterprise runtime integration | Not ready | Runtime supervision and event taxonomy are not wired. |
| Enterprise certification | Not ready | OI certification is not part of RC1/enterprise certification. |
| Live options readiness | Not ready | Live broker authority, option approvals, chain source, assignment, and execution are absent. |

## Architecture Scorecard

| Dimension | Score | Assessment |
| --- | ---: | --- |
| Architecture | 84 | Clear layered paper architecture with strong boundaries. |
| Modularity | 88 | Modules are focused and composable. |
| Reusability | 76 | Internals are reusable, but platform adapters are missing. |
| Maintainability | 84 | Deterministic code and docs support maintenance. |
| Scalability | 74 | Fine for paper certification; production scaling needs shared services. |
| Operational readiness | 76 | Good local readiness, missing runtime supervision. |
| Certification readiness | 82 | Strong paper certification, not enterprise-integrated. |
| Integration quality | 72 | Safe, but many connections are still local/read-model only. |
| Code organization | 86 | `backend/options` is coherent and traceable. |
| Enterprise alignment | 78 | Strong safety alignment, incomplete service consolidation. |
| Overall score | 82 | Ready for controlled paper governance; not live-production ready. |

## Final Recommendation

Preserve the Options Income Engine as implemented through OI-010.

Do not discard or rewrite it. It is a safe, additive, paper-only subsystem that provides useful controlled certification evidence. The next approved work should be integration-oriented: publish OI outputs into existing CSS enterprise services, add contract tests, and gradually retire duplicated local reporting/health/certification surfaces only after platform consumers are stable.

GO for controlled paper/read-only architectural integration planning.

NO-GO for live options execution, live broker options routing, production runtime activation, or any change that grants execution authority.
