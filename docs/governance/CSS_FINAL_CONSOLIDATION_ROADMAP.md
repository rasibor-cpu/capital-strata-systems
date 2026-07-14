# CSS Final Consolidation Roadmap

Date: 2026-07-14

Working branch: `css-unified-consolidation-2026-07-13`

Baseline reviewed: `fb3577a9d522a962d8db756fff2a79149deb27b6`

Source branch reviewed: `phase1-persistence-foundation`

Scope: repository-wide consolidation gap analysis and roadmap. This document
does not modify code, reconstruct another subsystem, merge branches,
cherry-pick commits, activate persistence, wire replay logic, restart CSS,
deploy CSS, update Desktop, or change broker/execution behavior.

## Completed Salvages

| Unit | Commit on consolidation branch | Evidence |
| --- | --- | --- |
| Evidence Hashing | `505545f81342a28f2cf36b7e9d9ab2a0797bf015` | `dashboard/runtime/evidence_hashing.py`, `tests/dashboard/test_evidence_hashing.py`, `docs/governance/CSS_CONSOLIDATION_PROGRESS.md` |
| Persistent Execution Journal | `2529cbdae39fab1fce2dbdf4e2d2c4961aadc15a` | `backend/app/audit/persistent_execution_journal.py`, `tests/dashboard/test_persistent_execution_journal.py`, `docs/governance/PERSISTENT_EXECUTION_JOURNAL_SALVAGE.md` |
| Runtime Event Normalization | `87e8a1f10c654419c11dcd4a965a157dd72c2cb5` | `backend/events/runtime_event_normalization.py`, `tests/dashboard/test_runtime_event_normalization.py`, `docs/governance/RUNTIME_EVENT_NORMALIZATION_SALVAGE.md` |
| Evidence Governance | `fb3577a9d522a962d8db756fff2a79149deb27b6` | `docs/governance/RUNTIME_EVENT_RETENTION_AND_EVIDENCE_GOVERNANCE.md` |

## Current Branch Subsystem Inventory

Status values:

- `COMPLETE`: implementation and direct test/runtime wiring evidence exist.
- `COMPLETE_PENDING_CERTIFICATION`: implementation and tests exist, but full
  production or release certification is still required.
- `PARTIAL`: implementation exists but is bounded, simulated, advisory,
  non-live, or missing important capability.
- `OBSERVER_ONLY`: read-only visibility/review capability exists, not an
  authority or state source.
- `PLACEHOLDER`: scaffolding, spec, disabled mode, or future-plug-in language is
  the main evidence.
- `NOT_PRESENT`: no implementation evidence was found in reviewed files.

| Subsystem | Status | Repository evidence | Gap or constraint |
| --- | --- | --- | --- |
| Runtime | COMPLETE_PENDING_CERTIFICATION | `backend/runtime/*` contains startup state, runtime certification, broker readiness, live authority, and operational proving modules; `dashboard/runtime/api_bridge.py` exposes runtime certification snapshot endpoints; tests include `tests/test_phase163b3a_runtime_certification_optimization.py`, `tests/test_phase164_operational_proving.py`, `tests/test_runtime_session_continuity.py`, and `tests/test_runtime_recovery_manager.py`. | Broad regression and runtime certification are still required before replacement of the old development line. |
| Authentication | COMPLETE_PENDING_CERTIFICATION | `backend/app/auth/*`, `backend/security/user_auth.py`, `dashboard/auth/css_sign_on.py`; tests include `tests/test_dashboard_auth_canonical.py`, `tests/test_signon_persistence_restoration.py`, `tests/test_phase165_coinbase_authentication_completion.py`, and `tests/test_phase165b_oanda_authentication_completion.py`. | Authentication has certification evidence, but live operational authentication still requires controlled validation and secret hygiene review. |
| Dashboard | COMPLETE_PENDING_CERTIFICATION | `dashboard/web/README.md` describes read-only dashboard routes; `dashboard/web/web_app.py` contains broker/live readiness pages and `live_trading_enabled` display defaults; dashboard tests include frontend payload, mobile, summary, broker, and runtime views. | Read-only dashboard surface is broad; browser/visual and production certification should run before merge. |
| Brokers | PARTIAL | `backend/app/brokers/*`, `backend/runtime/*read_only*`, `backend/validation/operational_broker_certifier.py`, and tests such as `tests/test_phase154a_broker_readiness_framework.py`, `tests/test_phase154b_broker_parity_validator.py`, `tests/test_phase156a_live_broker_validation.py`, and `tests/test_phase163b3j_broker_state_authority.py`. | Broker readiness and read-only validation exist, but this branch should not be treated as production-live broker execution ready. |
| Options | PARTIAL | `docs/architecture/CSS_OPTIONS_COMPLETION_MATRIX.md` classifies options execution as dry-run only, broker integration as placeholder, covered calls/cash-secured puts as placeholders, Wheel/assignment as not present; tests exist for lifecycle, Greeks, dashboard, and classification. | Live options broker integration, assignment, Wheel, rolling, covered calls, and cash-secured puts remain incomplete. |
| Futures | PARTIAL | `docs/architecture/CSS_FUTURES_COMPLETION_MATRIX.md` classifies futures execution/orchestration/dashboard/PnL as partial while lifecycle, contract intelligence, risk, and tests are present. | Live futures execution, broker-live margin/reconciliation, fill ingestion, and dedicated production controls remain incomplete. |
| Portfolio | COMPLETE_PENDING_CERTIFICATION | `backend/portfolio/*`, `backend/investment_committee/*`, `backend/analytics/portfolio_*`, and tests such as `tests/test_portfolio_decision_orchestrator.py`, `tests/test_portfolio_optimization_engine.py`, `tests/test_portfolio_risk_committee.py`, and `tests/test_portfolio_dashboard_integration.py`. | Implementation is extensive, but final certification and integration regression are still needed. |
| Analytics | COMPLETE_PENDING_CERTIFICATION | `backend/analytics/*`, `backend/intelligence/*`, and tests across `tests/analytics/*`, `tests/test_performance_analytics_engine.py`, `tests/test_phase139a_dashboard_and_api.py`, and related portfolio/optimization suites. | Analytics are advisory and must remain separated from execution authority until certified. |
| Risk | COMPLETE_PENDING_CERTIFICATION | `backend/app/risk/*`, `backend/risk/*`, `backend/governance/css_unified_trade_gate.py`, `backend/governance/css_gate_dashboard_adapter.py`; tests include `tests/engine/test_risk_governor.py`, `tests/test_dashboard_trade_gate_freeze.py`, and broker authority tests. | Risk controls exist, but merge readiness requires full regression of trade gates, live authority, and broker state authority. |
| Governance | COMPLETE_PENDING_CERTIFICATION | Large `docs/governance/*` corpus, `backend/governance/*`, AI governance agents under `backend/app/ai_governance/*`, and tests such as `tests/test_governance_auditor_agent.py`, `tests/test_unified_governance_coordinator.py`, and `tests/governance/*`. | Governance evidence is strong, but final release approval remains external to this roadmap. |
| Persistence | PARTIAL | SQLite infrastructure and migrations exist under `backend/app/persistence/*`; event store exists at `backend/events/event_store.py`; persistent execution journal exists at `backend/app/audit/persistent_execution_journal.py`. | Core persistence exists, but runtime event persistence is explicitly disabled/governance-only and must not be considered activated. |
| Audit | COMPLETE_PENDING_CERTIFICATION | `backend/app/audit/execution_audit_ledger.py`, `backend/app/audit/persistent_execution_journal.py`, `backend/security/audit_ledger.py`, `dashboard/runtime/operator_action_audit_ledger.py`, and tests for audit trail and persistent journal. | Audit surfaces need broad regression and certification package review. |
| Evidence | PARTIAL | `dashboard/runtime/evidence_hashing.py`, `docs/governance/RUNTIME_EVENT_RETENTION_AND_EVIDENCE_GOVERNANCE.md`, and evidence hashing tests exist. Historical signature/notarization/verification helper modules are not yet reconstructed. | Evidence hash foundation exists; verification, signature readiness, notarization readiness, and post-pilot archive helper code remain candidate work. |
| Replay | OBSERVER_ONLY | `backend/events/event_replay.py`, `backend/validation/historical_replay_engine.py`, `dashboard/runtime/replay_*`, `dashboard/runtime/trade_lifecycle_replay_*`, docs under `docs/replay/*`, and replay tests exist. | Replay must remain read-only and cannot become execution state. Further replay wiring is not approved by this roadmap. |
| Reporting | COMPLETE_PENDING_CERTIFICATION | `backend/reporting/*`, `backend/app/reporting_api.py`, `backend/app/reporting_store.py`, and tests such as `tests/test_reporting_framework.py`, `tests/test_reporting_portal.py`, and performance reporting tests. | Reporting should be included in broad regression before merge. |
| Certification | COMPLETE_PENDING_CERTIFICATION | `backend/certification/*`, `backend/validation/live_readiness_certification.py`, `backend/validation/operational_broker_certifier.py`, RC1/marathon validation modules, and tests including `tests/test_certification_engine.py`, `tests/test_phase152b_live_readiness_certification.py`, `tests/test_rc1_platform_certification.py`, and `tests/test_marathon_certification_engine.py`. | Certification engines exist, but this branch has not completed final production certification after consolidation. |

## Remaining Historical Work From `phase1-persistence-foundation`

Completed or conceptually absorbed sources excluded from code-bearing salvage:
`676950e`, `bbda834`, `a766c3a`, `44ecaea`, `9f74883`, `fe43a51`,
`e6b0f81`, `293f57e`, and `d8efba4`.

The tables below retain every remaining candidate commit SHA from the source
branch and classify it for consolidation.

### Persistence

| Commit | Purpose | Complexity | Duplication risk | Regression risk | Recommendation |
| --- | --- | --- | --- | --- | --- |
| `72864d3` | Persistence package and SQLite manager | Low | High | Low | SKIP_ALREADY_PRESENT |
| `d7dd574` | SQLite migration runner | Low | High | Low | SKIP_ALREADY_PRESENT |
| `7bf6bc9` | Session persistence migration | Low | High | Low | SKIP_ALREADY_PRESENT |
| `e6b1930` | Durable trade schema | Low | High | Low | SKIP_ALREADY_PRESENT |
| `487ebe9` | Durable PnL snapshot schema | Low | High | Low | SKIP_ALREADY_PRESENT |
| `652b597` | Base repository abstraction | Low | High | Low | SKIP_ALREADY_PRESENT |
| `9817d01` | Durable session repository | Low | High | Low | SKIP_ALREADY_PRESENT |
| `3b5aa74` | Durable trade repository | Medium | High | Medium | SKIP_SUPERSEDED |
| `8515942` | Durable PnL snapshot repository | Low | High | Low | SKIP_ALREADY_PRESENT |
| `b12a354` | Session repository injection into orchestrator | Medium | High | High | SKIP_SUPERSEDED |
| `524472b` | Central persistence service facade | Medium | High | Medium | SKIP_SUPERSEDED |
| `2c0f4ec` | Runtime session lifecycle persistence service | Medium | High | Medium | SKIP_SUPERSEDED |
| `892fb5b` | Runtime trade lifecycle persistence service | Medium | High | Medium | SKIP_SUPERSEDED |
| `61026ed` | Runtime PnL snapshot persistence service | Medium | High | Medium | SKIP_SUPERSEDED |
| `01a9d73` | Orchestrator with persistence-aware services | High | High | High | REJECT |
| `bda3422` | Durable trade-open persistence hook | Medium | High | High | SKIP_SUPERSEDED |
| `ed3b00b` | Durable runtime PnL snapshot hook | Medium | High | High | SKIP_SUPERSEDED |

### Runtime

| Commit | Purpose | Complexity | Duplication risk | Regression risk | Recommendation |
| --- | --- | --- | --- | --- | --- |
| `03b242f` | Repair integrations and begin dashboard separation | High | High | High | SKIP_SUPERSEDED |
| `4a5ad18` | Extract dashboard runtime state and services | High | High | High | SKIP_SUPERSEDED |
| `64d33e8` | Trade lifecycle execution state service | Medium | High | Medium | SKIP_ALREADY_PRESENT |
| `bb00c5c` | Shadow-route producers through event bus | High | Medium | High | REJECT |
| `cc95616` | Runtime event bus inspection surface | Medium | High | Medium | SKIP_ALREADY_PRESENT |
| `770c415` | Operator persistence simulation review surface | Medium | High | Medium | SKIP_SUPERSEDED |
| `0efd409` | Runtime event storage scenario reporting | Low | High | Low | SKIP_ALREADY_PRESENT |
| `789fe81` | Runtime event persistence dry-run report export | Low | High | Low | SKIP_ALREADY_PRESENT |
| `6ca9393` | Post-phone synchronization orchestrator state | High | High | High | SKIP_SUPERSEDED |

### Replay

| Commit | Purpose | Complexity | Duplication risk | Regression risk | Recommendation |
| --- | --- | --- | --- | --- | --- |
| `5fbe599` | Trade lifecycle events to replay sink | Medium | High | Medium | SKIP_ALREADY_PRESENT |
| `8607611` | Read-only lifecycle replay viewer | Medium | High | Medium | SKIP_ALREADY_PRESENT |
| `cc94ff0` | Operator replay lifecycle viewer table | Medium | High | Medium | SKIP_SUPERSEDED |
| `dc961f1` | Replay UI/runtime consistency validation | Medium | Medium | Medium | SKIP_SUPERSEDED |
| `9cc0467` | Replay correlation and lineage foundation | Low | High | Low | SKIP_ALREADY_PRESENT |

### Export, Evidence, And Reporting

| Commit | Purpose | Complexity | Duplication risk | Regression risk | Recommendation |
| --- | --- | --- | --- | --- | --- |
| `2aef8f6` | Post-pilot reconciliation evidence workflow | Medium | Low | Medium | RECONSTRUCT |
| `86d5495` | Post-pilot evidence archive export package | Medium | Low | Medium | RECONSTRUCT |
| `37876df` | Immutable post-pilot archive manifest hashing | Low | Low | Low | RECONSTRUCT |
| `38acdad` | Signed evidence packet readiness layer | Medium | Low | Medium | RECONSTRUCT |
| `05e2072` | Extend signed evidence packet readiness layer | Medium | Low | Medium | RECONSTRUCT |
| `e1407d7` | Evidence packet notarization readiness design | Low | Low | Low | RECONSTRUCT |
| `51a3735` | Evidence verification readiness layer | Medium | Low | Medium | RECONSTRUCT |
| `51389af` | Manual evidence verification checklist surface | Medium | Low | Medium | RECONSTRUCT |
| `f3d4b94` | Evidence verification checklist print export view | Medium | Low | Medium | RECONSTRUCT |
| `2221a6a` | Validate evidence verification print export view | Low | Medium | Low | SKIP_SUPERSEDED |
| `030275c` | Browser visual governance readiness validation | Low | Medium | Low | SKIP_SUPERSEDED |
| `c1d9781` | Phase 53 full system testing | Low | Medium | Low | SKIP_SUPERSEDED |

### Options

| Commit | Purpose | Complexity | Duplication risk | Regression risk | Recommendation |
| --- | --- | --- | --- | --- | --- |
| `8f71b21` | Options registry, governor, and dry-run adapter foundation | Medium | High | High | SKIP_SUPERSEDED |

### Futures

| Commit | Purpose | Complexity | Duplication risk | Regression risk | Recommendation |
| --- | --- | --- | --- | --- | --- |
| `6789459` | Futures contract registry and governance foundation | Medium | High | High | SKIP_SUPERSEDED |
| `97ebffb` | Dry-run futures execution adapter foundation | Medium | High | High | SKIP_SUPERSEDED |

### Broker

| Commit | Purpose | Complexity | Duplication risk | Regression risk | Recommendation |
| --- | --- | --- | --- | --- | --- |
| `3ad0165` | Broker live-readiness certification framework | Low | High | Low | SKIP_ALREADY_PRESENT |
| `e6ab6cd` | IBKR broker bootstrap and reconciliation scaffold | High | Medium | High | SKIP_SUPERSEDED |
| `a0ac8da` | Live mode capital guard | High | High | High | SKIP_SUPERSEDED |
| `51535bf` | Coinbase live balance hydration and display | High | High | High | SKIP_SUPERSEDED |
| `0a9c86a` | Coinbase live mode inheritance and runtime consistency | High | High | High | SKIP_SUPERSEDED |
| `8b87b7c` | Coinbase live broker mode and credential loading | High | High | High | SKIP_SUPERSEDED |
| `08e6823` | Unified execution mode authority across assets | High | High | High | SKIP_SUPERSEDED |
| `e596a96` | Institutional multi-broker live execution routing | High | Medium | Critical | REJECT |

### Dashboard

| Commit | Purpose | Complexity | Duplication risk | Regression risk | Recommendation |
| --- | --- | --- | --- | --- | --- |
| `760de5a` | Controlled micro-live pilot readiness dashboard | Medium | Low | Medium | RECONSTRUCT |
| `5b06f88` | Checklist print mobile containment assertions | Low | Medium | Low | SKIP_SUPERSEDED |
| `a64f2d9` | Non-executing micro-live pilot order intent package | Medium | Low | Medium | RECONSTRUCT |
| `ce17be2` | Coinbase non-executing micro-live dry-run probe | Medium | Low | Medium | RECONSTRUCT |
| `8b0b20a` | Operator approval and kill-switch evidence gate | Medium | Low | Medium | RECONSTRUCT |
| `d71ed7c` | Broker readiness confirmation package | Medium | Low | Medium | RECONSTRUCT |
| `39135c5` | Pre-pilot go/no-go evidence record | Medium | Low | Medium | RECONSTRUCT |
| `7d6c5ba` | Manual micro-live pilot checklist export pack | Medium | Low | Medium | RECONSTRUCT |
| `bf4577a` | Phase 54 pilot safety controls test | Low | Low | Low | SALVAGE |
| `d4eee30` | Phase 54 pilot safety compatibility surfaces | Medium | Medium | Medium | SKIP_SUPERSEDED |
| `f04af7f` | Phase 54 pilot safety compatibility surfaces | Medium | Medium | Medium | SKIP_SUPERSEDED |

### Governance

| Commit | Purpose | Complexity | Duplication risk | Regression risk | Recommendation |
| --- | --- | --- | --- | --- | --- |
| `332da42` | Institutional roadmap and companion app planning | Low | High | Low | SKIP_ALREADY_PRESENT |
| `c3a913d` | Controlled micro-live pilot runbook/evidence template | Low | High | Low | SKIP_ALREADY_PRESENT |
| `ef04757` | Micro-live pilot evidence archive index | Low | High | Low | SKIP_ALREADY_PRESENT |
| `a1dcf17` | Pilot packet print checklist | Low | High | Low | SKIP_ALREADY_PRESENT |
| `3b40e05` | Governance sign-off register | Low | High | Low | SKIP_ALREADY_PRESENT |
| `946f9ae` | Incident review worksheet | Low | High | Low | SKIP_ALREADY_PRESENT |
| `e7918f4` | Evidence bundle manifest | Low | High | Low | SKIP_ALREADY_PRESENT |
| `7d4877c` | Archive naming/retention policy | Low | High | Low | SKIP_ALREADY_PRESENT |
| `469591d` | Operator daily brief template | Low | High | Low | SKIP_ALREADY_PRESENT |
| `8663270` | No-go decision log | Low | High | Low | SKIP_ALREADY_PRESENT |
| `172dba6` | Readiness cross-reference map | Low | High | Low | SKIP_ALREADY_PRESENT |
| `523870c` | Operations index | Low | High | Low | SKIP_ALREADY_PRESENT |

### Broad Merge Or Obsolete Integration

| Commit | Purpose | Complexity | Duplication risk | Regression risk | Recommendation |
| --- | --- | --- | --- | --- | --- |
| `2d8d285` | Cross-asset execution orchestration foundation | High | High | High | SKIP_SUPERSEDED |
| `8e7ba38` | Portfolio governance risk foundation | Medium | High | Medium | SKIP_SUPERSEDED |
| `13f65d9` | Institutional capital allocation governor | Medium | High | Medium | SKIP_SUPERSEDED |
| `0221e58` | Unified risk execution gate foundation | Medium | High | Medium | SKIP_SUPERSEDED |
| `abf3efa` | Institutional execution audit ledger foundation | Medium | High | Medium | SKIP_SUPERSEDED |
| `58ae6a8` | Integrate institutional audit ledger into orchestration | High | High | High | REJECT |
| `bbdc520` | Broad orchestrator merge with institutional intelligence integration | High | High | Critical | REJECT |
| `caf254f` | Merge `main` into source branch | High | High | Critical | REJECT |
| `7f262fb` | Merge Phase 54 safety control fixes | High | High | Critical | REJECT |
| `0fae9de` | Cross-asset scanner and orchestrator unification | High | High | High | SKIP_SUPERSEDED |

## Remaining Approved Salvage Units

Ordered by value and risk:

1. Evidence verification readiness package: reconstruct `51a3735`,
   `51389af`, and `f3d4b94` as helper/test/governance surfaces only; no API or
   automatic export wiring.
2. Post-pilot evidence archive package: reconstruct `2aef8f6`, `86d5495`, and
   `37876df` as read-only helper/test surfaces using current evidence hashing
   and governance policy.
3. Evidence signature/notarization readiness: reconstruct `38acdad`,
   `05e2072`, and `e1407d7` as readiness metadata only; no cryptographic
   signing authority or external notarization service integration.
4. Micro-live evidence package: reconstruct `a64f2d9`, `ce17be2`, `8b0b20a`,
   `d71ed7c`, `39135c5`, and `7d6c5ba` only if governance confirms these
   non-executing artifacts are still required for certification.
5. Phase 54 pilot safety regression test: salvage `bf4577a` after confirming
   current API names; test-only if practical.

## Units To Reject Permanently

| Unit | Reason |
| --- | --- |
| `e596a96` multi-broker live execution routing | High-risk live routing work conflicts with current broker-state authority and live-trading controls. |
| `bb00c5c` runtime producer shadow routing | Would change runtime delivery behavior and is outside current read-only normalization/governance scope. |
| `01a9d73`, `58ae6a8`, `bbdc520`, `caf254f`, `7f262fb` broad orchestrator/merge commits | Too broad, obsolete, and likely to overwrite newer current architecture. |
| Historical dashboard/API wiring bundled with evidence commits | Current branch requires manual reconstruction of helpers first; API/web wiring needs separate approval. |
| Any commit that changes broker adapters, credential loading, live mode inheritance, or execution routing without a dedicated broker authority milestone | These changes risk PCNRASS, MAEP, broker-state authority, authentication, and execution-governance controls. |

## Units Already Duplicated

- Core SQLite persistence (`72864d3` through `8515942`) is already present under
  `backend/app/persistence/*`.
- Runtime event bus, inspector, policy, report, simulator, replay correlation,
  replay envelopes, and lifecycle replay helpers are already present under
  `dashboard/runtime/*`.
- Micro-live operations docs are already present under `docs/operations/*`.
- Options/futures dry-run foundations are superseded by current
  `backend/app/options/*`, `backend/app/futures/*`, lifecycle adapters, and
  completion matrices.
- Broker readiness certification is already present in current broker/runtime
  validation modules and tests.

## Merge Readiness Criteria

Before merging `css-unified-consolidation-2026-07-13` back into the main
development line:

1. Working tree is clean except approved pre-existing untracked runtime/report
   artifacts, or those artifacts are explicitly quarantined outside the merge
   process.
2. All consolidation roadmap items accepted for merge are either completed,
   documented as deferred, or rejected with rationale.
3. Full finite regression suite passes for runtime, authentication, dashboard,
   broker state authority, options, futures, persistence, audit, evidence,
   replay, reporting, portfolio, analytics, risk, governance, and certification.
4. No runtime event persistence activation has been introduced.
5. No broker adapter, execution routing, live-trading control, credential,
   `.env`, PEM, Desktop, deployment, or runtime database change is included
   without explicit milestone approval.
6. Options/futures dry-run and live-disabled boundaries remain documented and
   tested.
7. Persistent execution journal and evidence hashing remain append-only,
   deterministic, redacted, and non-authoritative for trading state.
8. Production certification package is generated after final regression, not
   inferred from historical docs.
9. A final branch diff against `css-evening-consolidation-2026-06-09` is
   reviewed for unexpected source-code changes.
10. Merge commit or PR includes this roadmap, the consolidation progress log,
    and final validation evidence.

## Readiness Assessment

### 1. Is this branch safer than `css-evening-consolidation-2026-06-09`?

Yes, for the consolidated audit/evidence surface. Repository evidence: the
branch adds deterministic evidence hashing, the persistent execution journal,
runtime event normalization, and the evidence governance policy on top of
`css-evening-consolidation-2026-06-09`. It also tags the Stage 1 baseline at
`v1.0.0-consolidation-stage1`.

This does not mean it is broader-production safer. The safety improvement is
specific to observability, auditability, and consolidation governance.

### 2. Is it ready for broader regression testing?

Yes. Focused salvage validations have passed in prior milestones, and the
branch now has a documented roadmap. The correct next step is broader finite
regression, not another subsystem salvage.

### 3. Is it ready for production certification?

No. Certification engines and documents exist, but current evidence still shows
key partial areas: options live execution and broker integration are partial or
placeholder, futures live execution and broker-live reconciliation are partial,
and runtime event persistence remains disabled/governance-only. Production
certification must follow broad regression and final evidence packaging.

### 4. Is it ready to replace the old development branch?

Not yet. It is ready to be tested as the consolidation candidate, but it should
not replace the old development branch until full regression, final diff review,
final certification evidence, and merge approval are complete.

## Recommended First Code-Bearing Salvage After This Roadmap

Reconstruct the evidence verification readiness package from `51a3735`,
`51389af`, and `f3d4b94`.

Boundary:

- helper/test/governance surfaces only;
- reuse current `dashboard/runtime/evidence_hashing.py`;
- no API/web automatic export wiring;
- no runtime persistence activation;
- no replay wiring;
- no broker, execution, authentication, Desktop, deployment, or live-trading
  changes.

Rationale: it builds directly on the completed evidence hashing and governance
work, has low broker/execution risk, and improves certification readiness more
than another broad runtime or broker salvage.
