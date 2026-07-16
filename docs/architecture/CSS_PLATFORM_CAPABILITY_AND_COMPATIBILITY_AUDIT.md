# CSS Platform Capability And Compatibility Audit

Phase: PCA-001

Audit Date: 2026-07-16

Baseline Branch: css-unified-consolidation-2026-07-13

Baseline Commit SHA: 502fb70587b0597873a7a2531589cc6d75261220

Audit Mode: Evidence-only, no implementation changes, no live execution.

## Safety Posture (Verified)

Required safety boundary is preserved across runtime, broker readiness, Mission Control, and certification artifacts:

- execution_allowed=false
- live_trading_blocked=true
- broker_execution_armed=false
- advisory_only=true

Representative code/test evidence:

- backend/runtime/canonical_broker_state_builder.py
- backend/runtime/runtime_certification_snapshot.py
- backend/runtime/broker_environment_profiles.py
- dashboard/mission_control/routes.py
- tests/test_phase166c_canonical_runtime_state_final_reconciliation.py
- tests/test_phase166d_live_environment_contamination_elimination.py
- tests/test_mc007c_production_hardening.py
- tests/test_oi010_certification.py

## Repository Verification

Pre-work verification commands executed:

- git branch --show-current
- git rev-parse HEAD
- git rev-parse origin/css-unified-consolidation-2026-07-13
- git status --short
- git log -10 --oneline

Findings:

- Current branch is css-unified-consolidation-2026-07-13.
- Local HEAD equals origin: 502fb70587b0597873a7a2531589cc6d75261220.
- No tracked modifications were present before audit docs; pre-existing untracked runtime/report artifacts remained unstaged.

## Subsystem Inventory (Authoritative Summary)

Status taxonomy used exactly as required.

| ID | Subsystem | Purpose | Primary Modules | Entry Points / Hosts | Status | Safety Posture | Known Limitations |
|---|---|---|---|---|---|---|---|
| SYS-001 | Runtime Supervision | Runtime health, restart, continuity | backend/runtime/css_runtime_supervisor.py, backend/runtime/runtime_supervisor.py | launcher/css_runtime_launcher.py | COMPLETE_PENDING_CERTIFICATION | Advisory-only enforced | Desktop persistence variability across hosts |
| SYS-002 | Runtime Artifact Publishing | Cross-process state publication | backend/runtime/runtime_artifact_publisher.py | launcher/css_mobile_launcher.py runtime readers | COMPLETE_PENDING_CERTIFICATION | execution_allowed false in payloads | File artifact freshness dependency |
| SYS-003 | Mission Control Core | Operational visibility plane | dashboard/mission_control/* | dashboard/web/web_app.py, launcher/css_mobile_launcher.py | COMPLETE_CERTIFIED | GET-only and read-only route enforcement | Certification is test/document heavy |
| SYS-004 | Frontend Contract Bridge | Canonical dashboard payload | dashboard/runtime/frontend_contract.py | dashboard/web/web_app.py API routes | COMPLETE_PENDING_CERTIFICATION | Read-only contract and redaction | Legacy compatibility fields remain |
| SYS-005 | Broker Env Profiles (BR-001) | Strict paper/live profile isolation | backend/runtime/broker_environment_profiles.py, backend/runtime/live_environment_loader.py | runtime loader path and startup loaders | COMPLETE_PENDING_CERTIFICATION | Live blocked, contamination removal | Legacy file/profile migration complexity |
| SYS-006 | Canonical Broker State | Unified broker readiness/status authority | backend/runtime/canonical_broker_state_builder.py | frontend contract and startup summary | COMPLETE_PENDING_CERTIFICATION | hard fail-closed flags | Multi-source status duplication |
| SYS-007 | Coinbase Read-only Readiness | Coinbase credential/read checks | backend/runtime/coinbase_readiness.py | scripts/css_live_dashboard.py | COMPLETE_PAPER_ONLY | live authority blocked | Live execution unsupported |
| SYS-008 | OANDA Read-only Readiness | OANDA credential/read checks | backend/runtime/oanda_readiness.py | scripts/css_live_dashboard.py | COMPLETE_PAPER_ONLY | live authority blocked | Live execution unsupported |
| SYS-009 | IBKR Adapter Layer | IBKR placeholder connectivity/adapters | backend/brokers/ibkr/ibkr_adapter.py | backend/brokers/ibkr/ibkr_runtime_manager.py | PARTIALLY_IMPLEMENTED | no live authority path | No production-grade IBKR integration |
| SYS-010 | Trading Orchestration | Signal-to-decision flow | engine/execution_router.py, engine/decision_builder.py | engine/run_engine.py | COMPLETE_ADVISORY_ONLY | gate and firewall layers | Host activation inconsistency |
| SYS-011 | Strategy Orchestration | Strategy selection and routing | backend/strategies/*, engine/strategy/* | dashboard/runtime and engine loop | COMPLETE_ADVISORY_ONLY | no automatic live routing | Strategy readiness varies by asset class |
| SYS-012 | Market Intelligence | Regime/factor intelligence | backend/market_intelligence/*, backend/intelligence/* | dashboard sections and APIs | COMPLETE_PENDING_CERTIFICATION | advisory outputs | Cross-process stale risk if artifacts old |
| SYS-013 | Portfolio State | Portfolio lifecycle and summaries | backend/portfolio/*, backend/runtime/runtime_portfolio_lifecycle.py | frontend contract, Mission Control | COMPLETE_PENDING_CERTIFICATION | advisory-only projection | Accounting reconciliation depth varies |
| SYS-014 | Capital Allocation | Capital and opportunity allocation | backend/runtime/caie_runtime_bridge.py, backend/options/options_income_allocator.py | dashboard intelligence sections | COMPLETE_ADVISORY_ONLY | constrained/no execution | Production calibration pending |
| SYS-015 | Risk Governance | Risk scoring, stress, committees | backend/risk/*, backend/options/options_income_risk_governance.py | risk APIs and dashboards | COMPLETE_PENDING_CERTIFICATION | hard blocked execution | Duplicate risk summaries across layers |
| SYS-016 | Execution Pipeline | Unified execution abstraction | engine/execution/*, backend/execution/* | execution router paths | PARTIALLY_IMPLEMENTED | fail-closed by default | Live pathways intentionally blocked |
| SYS-017 | Paper Trading | Controlled paper operations | backend/options/options_paper_broker.py, engine/sim/* | OI and paper broker paths | COMPLETE_CERTIFIED | paper_only true | Not live-authority capable |
| SYS-018 | Options Core Lifecycle | Option lifecycle and Greeks | backend/options/options_* core modules | options dashboards/tests | COMPLETE_PENDING_CERTIFICATION | non-executable posture | Advanced spread families not in canonical scope |
| SYS-019 | Options Income Engine OI-001..010 | Income strategy domain and lifecycle | backend/options/options_income_* | internal adapters and test routers | COMPLETE_PAPER_ONLY | strict paper/advisory flags | Host activation limited |
| SYS-020 | Options Enterprise Integration EI-001/RC1-OI | Enterprise adapters and certification hooks | backend/options/options_income_rc1_* | test-host registries, report builders | INTEGRATED_NOT_HOST_ACTIVATED | safe flags enforced | Not wired into production host runtime |
| SYS-021 | Shared Derivatives Services | Exposure/stress/volatility services | backend/derivatives/* | consumed by RC1-OI integration | COMPLETE_PENDING_CERTIFICATION | advisory-safe payloads | Limited broad host consumers |
| SYS-022 | Treasury Capability | Liquidity/cash management surfaces | engine/liquidity/*, engine/fiscal/* | analytics/report layers | PARTIALLY_IMPLEMENTED | advisory only | Institutional treasury roadmap largely open |
| SYS-023 | Audit/Event Infrastructure | Event bus and audit records | backend/events/*, backend/options/options_income_event_adapter.py | certification adapters and run reports | COMPLETE_PENDING_CERTIFICATION | redaction and fail-closed patterns | Runtime ownership/persistence ambiguity |
| SYS-024 | Alerts/Notifications | Alert generation/delivery | backend/notifications/*, tests/test_notification_* | dashboard/mobile surfaces | COMPLETE_PENDING_CERTIFICATION | no execution authority | Delivery channels partly simulation-oriented |
| SYS-025 | Explainability | Decision explanation surfaces | backend/options/options_income_explainability.py, backend/intelligence/* | dashboard + Mission Control | COMPLETE_PENDING_CERTIFICATION | advisory-only | Explainability schema duplication |
| SYS-026 | Learning/Analytics | Feedback and learning loops | backend/learning/*, options learning adapters | dashboard analytics and cert adapters | COMPLETE_PENDING_CERTIFICATION | no direct execution effect | Production drift controls still maturing |
| SYS-027 | Certification/Readiness | RC1, runtime, broker cert | backend/validation/*, backend/runtime/runtime_certification_snapshot.py | release docs and dashboard sections | COMPLETE_PENDING_CERTIFICATION | safety checks explicit | Heavy reliance on test-driven evidence |
| SYS-028 | Dashboard Web Host | Institutional web host + APIs | dashboard/web/web_app.py | FastAPI web app | COMPLETE_PENDING_CERTIFICATION | read-only route model | Desktop operational proof not equivalent to broad prod rollout |
| SYS-029 | Mobile Dashboard Host | Launcher mobile host | launcher/css_mobile_launcher.py | uvicorn launcher module | COMPLETE_PENDING_CERTIFICATION | controls constrained; no live arming evidence | Large monolithic launcher complexity |
| SYS-030 | RBAC/Auth Surfaces | Auth, permissions, recovery | dashboard/auth/*, dashboard/mission_control/permissions.py | dashboard and mission control consoles | PARTIALLY_IMPLEMENTED | read-only emphasis | Enterprise auth hardening still mixed |
| SYS-031 | Deployment/Operations Docs | runbooks and deployment governance | docs/runbooks/*, docs/deployment/* | documentation consumed by operators | COMPLETE_PENDING_CERTIFICATION | policy-level safeguards | Operational validation still mostly controlled environments |
| SYS-032 | Legacy/Build Scripts Footprint | historical patch scripts | scripts/build_* | non-host patch utilities | DEPRECATED | not in live runtime path | Drift/confusion risk if reused |

## Capability Classification Highlights

1. Genuinely complete now:
- Mission Control read-only visibility plane and API surface (MC-001..MC-007C) with host registrations in web and mobile hosts.
- Broker environment profile separation and contamination controls for paper/live profile loading.
- Canonical broker runtime state projection and front-end adapter integration.
- OI-001..OI-010 paper/advisory capability stack with deterministic certification harness.

2. Complete only for paper/advisory use:
- Options Income strategy execution lifecycle, risk, dashboard, broker abstraction, and certification.
- Runtime readiness/certification and broker validation stack.
- RC1 platform and RC1-OI final verdicts (controlled release posture only).

3. Integrated but not host-activated:
- Options Income API router and RC1 enterprise integration adapters are strongly implemented and tested, but production host route registration is not demonstrated in runtime host wiring.

4. Certified:
- RC1 paper/advisory release readiness documents and corresponding certification tests.
- Mission Control v1.0 final certification in tests and governance docs.
- OI-010 and RC1-OI certification suites.

5. Incomplete:
- Production live execution authority pipeline.
- Broad production deployment evidence beyond controlled/desktop proof.
- Institutional treasury and advanced derivatives roadmap items.
- IBKR production-grade integration.

6. Duplications observed:
- Multiple broker status and readiness payload projections.
- Repeated safety/status flags in multiple adapters.
- Overlap across runtime snapshot, frontend contract, and Mission Control state projection layers.

7. Incompatibilities observed:
- Some legacy/startup script paths still carry old assumptions and broad global state, creating compatibility warnings with canonical profile/state architecture.

8. Approved roadmap items remaining:
- Advanced derivatives families, institutional treasury stack, multi-currency hedging, deployment hardening, and secure live onboarding pathways.

9. Highest marginal value candidate:
- Canonical host activation of Options Income enterprise integration (runtime + dashboard + Mission Control panels) with cross-process evidence and compatibility contract stabilization.

## Options Income Engine Deep Audit Conclusion

Evidence reviewed:

- backend/options/options_income_*
- backend/options/options_income_rc1_*
- tests/test_oi002_income_strategy_domain_model.py through tests/test_oi010_certification.py
- tests/test_ei001_options_enterprise_integration.py
- tests/test_rc1_oi_enterprise_integration_certification.py

Conclusion:

- Functional scope for canonical OI program is complete for paper/advisory operation: covered calls, cash-secured puts, rolling, position management, portfolio construction, risk budgets, Greeks, assignment and volatility risk handling, stress testing, and dashboard intelligence.
- Broker integration is paper abstraction complete and enterprise-adapter integrated.
- Runtime and host activation is not fully demonstrated for production host wiring of OI routes/panels; classify as COMPLETE_PAPER_ONLY with INTEGRATED_NOT_HOST_ACTIVATED components.
- Certification is strong for paper-only scope; live execution capability remains blocked by design.

Optional strategies not required by canonical OI scope remain not implemented as autonomous production strategies:

- Spreads (complex multi-leg automation)
- Iron condors
- Calendar/diagonal automation
- Wheel automation
- LEAPS income automation

These are roadmap opportunities, not current-scope failures.

## Mission Control Deep Audit Conclusion

Evidence reviewed:

- dashboard/mission_control/*
- dashboard/web/web_app.py
- launcher/css_mobile_launcher.py
- tests/test_mc001_mission_control_foundation.py through tests/test_mc007c_production_hardening.py

Conclusion:

- Mission Control v1.0 is feature-complete for read-only operational command-plane objectives.
- Host-activated in both web host and mobile launcher.
- Runtime-compatible through runtime snapshot provider and source resolver chain with fail-closed behavior.
- Operational validation is strong in test suites and controlled Desktop evidence docs.
- Production-certified status should be interpreted as controlled/read-only certification; broad real-world desktop endurance evidence remains comparatively limited.

Classification: COMPLETE_CERTIFIED for read-only operational surface, with COMPATIBLE_WITH_WARNINGS for broad production activation assumptions.

## Compatibility Audit Summary

See detailed matrix in CSS_PLATFORM_COMPATIBILITY_MATRIX.md.

High-confidence compatible links:

- runtime snapshot -> Mission Control
- runtime snapshot -> mobile dashboard
- frontend contract -> dashboard hosts
- canonical broker state -> broker diagnostics/readiness adapters
- broker environment profiles -> credential loaders/readiness paths

Compatible with warnings:

- Options Income -> Mission Control (panel/test wiring evidence exists, broad host runtime activation remains partial)
- certification -> RC1 readiness (test/document certified, controlled operational evidence)
- deployment scripts -> canonical runtime architecture (legacy launcher/script breadth may diverge)

Unverified or partial areas:

- cross-process production endurance for all runtime artifact consumers
- IBKR parity in production-grade pathways

## Duplication And Consolidation Summary

See detailed register in CSS_PLATFORM_DUPLICATION_AND_CONSOLIDATION_REGISTER.md.

Highest-risk duplication clusters:

- Broker readiness/status projections
- Runtime snapshot/state hash/freshness adapters
- Safety flag propagation wrappers
- Environment/credential alias handling

## Host Activation Audit Summary

Runtime-active and host-active:

- Mission Control host registration and routes in dashboard and mobile hosts.
- Frontend contract API and dashboard surfaces.

Implemented but not clearly host-activated in production runtime:

- Options Income API router and enterprise-integration route surface.
- Several certification adapters and enterprise wrappers consumed primarily in tests/certification pipelines.

Adapter-only/test-only signals:

- RC1-OI host integration contracts via in-memory host registries in tests.
- IBKR adapters with placeholder behavior.

## Test And Certification Audit Summary

Focused representative slices executed during PCA-001:

- python -m pytest tests/test_mc007c_production_hardening.py -q
- python -m pytest tests/test_oi010_certification.py -q
- python -m pytest tests/test_rc1_oi_enterprise_integration_certification.py -q
- python -m pytest tests/test_br001_broker_environment_profiles.py tests/test_phase166d_live_environment_contamination_elimination.py tests/test_phase156b_live_connectivity_certifier.py -q

All executed slices passed in this audit run.

Gaps and risks:

- Full repository suite not run due to scope/hang risk.
- Desktop operational validation exists but broad production endurance remains limited.
- Large launcher script complexity increases regression/test fragility risk.

## Roadmap Gap Audit Summary

See roadmap document for full classification.

Notable remaining areas:

- Institutional portfolio optimization completion depth and production activation
- Treasury and liquidity institutionalization
- FX forwards/swaps and cross-currency hedging
- Live broker execution governance and secure onboarding
- Institutional reporting and mobile operations hardening at production scale

## Highest-Value Improvement Analysis (Top 5)

1. Canonical host activation for Options Income enterprise services
2. Broker readiness/canonical state consolidation to one authority payload
3. Runtime artifact ownership and freshness contract hardening across processes
4. Mission Control and frontend payload schema simplification and de-duplication
5. Deployment and production endurance evidence automation

Primary recommendation: Option 1.

Fallback recommendation: Option 2.

## Technical Debt And Risk Register (Summary)

Top risks:

- Duplicate service projections across runtime/dashboard layers
- Stale aliases and compatibility fields
- Environment loading/credential alias complexity
- Cross-process artifact freshness and ownership ambiguity
- Host activation gaps for implemented enterprise adapters
- Monolithic launcher risk and test fragility

Detailed register with severity/probability/action is in governance and duplication documents.

## Platform Readiness Scorecard

Scores are conservative and bounded by evidence quality.

| Area | Score | Why Not Higher |
|---|---:|---|
| Architecture | 83 | Duplication and legacy overlap remain |
| Runtime | 81 | Cross-process artifact and launcher complexity risks |
| Trading | 74 | Advisory-first, execution pathways intentionally constrained |
| Portfolio | 79 | Strong modeling; production-scale evidence limited |
| Risk | 82 | Robust governance modules; consolidation needed |
| Broker | 77 | Coinbase/OANDA strong read-only, IBKR partial |
| Execution | 58 | Live execution authority intentionally blocked |
| Options | 80 | Core lifecycle mature; advanced strategy automation deferred |
| Options Income | 86 | Strong paper/advisory completion, host activation gap |
| Derivatives | 73 | Shared services present; broader host consumers limited |
| Treasury | 41 | Partial implementation and roadmap-heavy |
| Audit | 80 | Strong adapters and reports; persistence ownership unclear |
| Alerts | 76 | Good framework coverage; channel hardening pending |
| Explainability | 78 | Strong model outputs; schema duplication exists |
| Learning | 75 | Mature adapters, production drift controls pending |
| Certification | 88 | Extensive certification suites and docs |
| Dashboard | 84 | Mature contracts and routes, legacy overlap |
| Mobile | 72 | Host active but monolithic runtime wrapper risk |
| Mission Control | 90 | Feature complete and host activated read-only plane |
| Governance | 87 | Broad policy and reports; some doc-code drift risk |
| Deployment | 63 | Controlled readiness strong, full production proof limited |
| Live Readiness | 28 | Explicitly blocked by design and policy |

Aggregate metrics:

- Overall Platform Score: 76
- Controlled Paper Readiness: 90
- Operational Readiness: 78
- Production Deployment Readiness: 64
- Live Trading Readiness: 28

## Overall Verdict

Verdict: CONDITIONAL GO

Interpretation:

- GO for controlled paper/advisory operation and continued integration hardening.
- Not a GO for live execution enablement or unrestricted production trading.

Conditions:

1. Keep hard safety flags immutable.
2. Prioritize Options Income host activation and compatibility stabilization.
3. Reduce canonical-state duplication before any broader production rollout.
4. Preserve strict broker environment profile separation.

## Evidence Priority Rule

Where code/tests and documents differ, code and executable tests govern this audit.

UNVERIFIED labels were used where direct executable or host evidence was insufficient.
