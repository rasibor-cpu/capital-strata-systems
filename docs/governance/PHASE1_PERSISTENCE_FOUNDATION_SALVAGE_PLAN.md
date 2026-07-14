# Phase1 Persistence Foundation Salvage Plan

Created: 2026-07-14

Current consolidation branch: `css-unified-consolidation-2026-07-13`

Current consolidation baseline SHA: `c2c4d588df2710b23548e49bffe0b9aa337639e9`

Candidate branch reviewed: `phase1-persistence-foundation`

Candidate branch HEAD: `0fae9decac055e5ccfb4e6ca596b086a587bdf47`

Unique commit count versus consolidation branch: 97

Scope rule: this plan is review-only. No merge, cherry-pick, source reconstruction, broker change, execution change, runtime restart, deployment, Desktop update, or branch deletion is authorized by this document.

## Summary Finding

`phase1-persistence-foundation` is not safe for wholesale merge. The branch contains valuable historical work, but the current consolidation branch already contains much of the persistence, event bus, replay, options, futures, and documentation work, often in identical or newer form.

Unique-file comparison against `css-unified-consolidation-2026-07-13`:

| Comparison result | Count | Meaning |
| --- | ---: | --- |
| `ALREADY_IDENTICAL` | 49 | Candidate file content is already present byte-for-byte in current consolidation branch. |
| `DIFFERS_FROM_CURRENT` | 44 | Candidate file exists in both branches but current branch has different content. Most should be treated as newer current implementation unless a specific missing behavior is proven. |
| `MISSING_IN_CURRENT` | 64 | Candidate file is absent from current branch and may contain salvageable work. |

## Unique Commits Grouped By Area

### Persistence

| Commit | Purpose | Initial action |
| --- | --- | --- |
| `72864d3` | Initialize persistence package and SQLite manager | SKIP_ALREADY_PRESENT |
| `d7dd574` | Add SQLite migration runner | SKIP_ALREADY_PRESENT |
| `7bf6bc9` | Add session migration | SKIP_ALREADY_PRESENT |
| `e6b1930` | Add durable trade schema | SKIP_ALREADY_PRESENT |
| `487ebe9` | Add PnL snapshot schema | SKIP_ALREADY_PRESENT |
| `652b597` | Add base repository abstraction | SKIP_ALREADY_PRESENT |
| `9817d01` | Add session repository | SKIP_ALREADY_PRESENT |
| `3b5aa74` | Add trade repository | SKIP_SUPERSEDED |
| `8515942` | Add PnL snapshot repository | SKIP_ALREADY_PRESENT |
| `b12a354` | Inject session persistence into orchestrator | SKIP_SUPERSEDED |
| `524472b` | Add persistence service facade | SKIP_SUPERSEDED |
| `2c0f4ec` | Add runtime session lifecycle persistence service | SKIP_SUPERSEDED |
| `892fb5b` | Add runtime trade lifecycle persistence service | SKIP_SUPERSEDED |
| `61026ed` | Add runtime PnL snapshot persistence service | SKIP_SUPERSEDED |
| `01a9d73` | Restore orchestrator with persistence-aware services | SKIP_SUPERSEDED |
| `bda3422` | Add durable trade-open persistence hook | SKIP_SUPERSEDED |
| `ed3b00b` | Add durable runtime PnL snapshot hook | SKIP_SUPERSEDED |

### Broker

| Commit | Purpose | Initial action |
| --- | --- | --- |
| `3ad0165` | Add broker live-readiness certification framework | SKIP_ALREADY_PRESENT |
| `e6ab6cd` | Add IBKR broker bootstrap and reconciliation scaffold | SKIP_SUPERSEDED |
| `a0ac8da` | Fix live mode capital guard | SKIP_SUPERSEDED |
| `51535bf` | Stabilize Coinbase live balance hydration and display | SKIP_SUPERSEDED |
| `0a9c86a` | Fix Coinbase live mode inheritance and runtime consistency | SKIP_SUPERSEDED |
| `8b87b7c` | Stabilize Coinbase live broker mode and credential loading | SKIP_SUPERSEDED |
| `08e6823` | Enforce unified execution mode authority across assets | SKIP_SUPERSEDED |
| `e596a96` | Enable institutional multi-broker live execution routing | REJECT_UNSAFE |

### Options

| Commit | Purpose | Initial action |
| --- | --- | --- |
| `8f71b21` | Add options registry, governor, and dry-run adapter foundation | SKIP_SUPERSEDED |

### Futures

| Commit | Purpose | Initial action |
| --- | --- | --- |
| `6789459` | Add futures contract registry and governance foundation | SKIP_SUPERSEDED |
| `97ebffb` | Add dry-run futures execution adapter foundation | SKIP_SUPERSEDED |

### Runtime

| Commit | Purpose | Initial action |
| --- | --- | --- |
| `03b242f` | Repair integrations and begin dashboard separation | SKIP_SUPERSEDED |
| `4a5ad18` | Extract dashboard runtime state and services | SKIP_SUPERSEDED |
| `64d33e8` | Extract trade lifecycle execution state service | SKIP_ALREADY_PRESENT |
| `a766c3a` | Add canonical runtime event bus foundation | SKIP_ALREADY_PRESENT |
| `bb00c5c` | Shadow-route producers through event bus | SKIP_SUPERSEDED |
| `cc95616` | Add runtime event bus inspection surface | SKIP_ALREADY_PRESENT |
| `fe43a51` | Add runtime event retention/export policy | SKIP_ALREADY_PRESENT |
| `e6b0f81` | Add guarded runtime event persistence approval framework | SKIP_SUPERSEDED |
| `44ecaea` | Define runtime event persistence architecture | SKIP_ALREADY_PRESENT |
| `9f74883` | Add dry-run runtime event persistence simulator | SKIP_ALREADY_PRESENT |
| `770c415` | Add operator persistence simulation review surface | SKIP_SUPERSEDED |
| `0efd409` | Add runtime event storage scenario reporting | SKIP_ALREADY_PRESENT |
| `789fe81` | Add runtime event persistence dry-run report export | SKIP_ALREADY_PRESENT |
| `293f57e` | Add runtime event persistence operator checklist | SALVAGE_FILES_ONLY |
| `d8efba4` | Add persistence checklist export print view | SALVAGE_FILES_ONLY |

### Replay

| Commit | Purpose | Initial action |
| --- | --- | --- |
| `5fbe599` | Wire trade lifecycle events to replay sink | SKIP_ALREADY_PRESENT |
| `8607611` | Expose lifecycle replay through read-only viewer | SKIP_ALREADY_PRESENT |
| `cc94ff0` | Add operator replay lifecycle viewer table | SKIP_SUPERSEDED |
| `dc961f1` | Validate replay UI/runtime consistency | SKIP_SUPERSEDED |
| `9cc0467` | Add replay correlation and lineage foundation | SKIP_ALREADY_PRESENT |

### Dashboard And Evidence

| Commit | Purpose | Initial action |
| --- | --- | --- |
| `760de5a` | Add controlled micro-live pilot readiness dashboard | SALVAGE_FILES_ONLY |
| `5b06f88` | Add checklist print mobile containment assertions | SALVAGE_FILES_ONLY |
| `a64f2d9` | Add non-executing micro-live pilot order intent package | SALVAGE_FILES_ONLY |
| `ce17be2` | Add Coinbase non-executing micro-live dry-run probe | SALVAGE_FILES_ONLY |
| `8b0b20a` | Add operator approval and kill-switch evidence gate | SALVAGE_FILES_ONLY |
| `d71ed7c` | Add broker readiness confirmation package | SALVAGE_FILES_ONLY |
| `39135c5` | Add pre-pilot go/no-go evidence record | SALVAGE_FILES_ONLY |
| `7d6c5ba` | Add manual pilot checklist export pack | SALVAGE_FILES_ONLY |
| `676950e` | Add immutable evidence hashing foundation | SALVAGE_FILES_ONLY |
| `f023991` | Add operator action audit ledger foundation | SKIP_ALREADY_PRESENT |
| `2aef8f6` | Add post-pilot reconciliation evidence workflow | SALVAGE_FILES_ONLY |
| `86d5495` | Add post-pilot evidence archive export package | SALVAGE_FILES_ONLY |
| `37876df` | Add immutable archive manifest hashing | SALVAGE_FILES_ONLY |
| `38acdad` | Add signed evidence packet readiness layer | SALVAGE_FILES_ONLY |
| `05e2072` | Extend signed evidence packet readiness layer | SALVAGE_FILES_ONLY |
| `e1407d7` | Add notarization readiness design | SALVAGE_FILES_ONLY |
| `51a3735` | Add evidence verification readiness layer | SALVAGE_FILES_ONLY |
| `51389af` | Add manual evidence verification checklist surface | SALVAGE_FILES_ONLY |
| `f3d4b94` | Add evidence verification checklist print export view | SALVAGE_FILES_ONLY |
| `2221a6a` | Validate evidence verification print export view | SKIP_SUPERSEDED |
| `030275c` | Validate browser visual governance readiness | SKIP_SUPERSEDED |
| `c1d9781` | Complete Phase 53 full system testing | SKIP_SUPERSEDED |

### Governance

| Commit | Purpose | Initial action |
| --- | --- | --- |
| `332da42` | Update institutional roadmap and companion app planning | SKIP_ALREADY_PRESENT |
| `c3a913d` | Add controlled micro-live pilot runbook/evidence template | SKIP_ALREADY_PRESENT |
| `ef04757` | Add micro-live pilot evidence archive index | SKIP_ALREADY_PRESENT |
| `a1dcf17` | Add pilot packet print checklist | SKIP_ALREADY_PRESENT |
| `3b40e05` | Add governance sign-off register | SKIP_ALREADY_PRESENT |
| `946f9ae` | Add incident review worksheet | SKIP_ALREADY_PRESENT |
| `e7918f4` | Add evidence bundle manifest | SKIP_ALREADY_PRESENT |
| `7d4877c` | Add archive naming/retention policy | SKIP_ALREADY_PRESENT |
| `469591d` | Add operator daily brief template | SKIP_ALREADY_PRESENT |
| `8663270` | Add no-go decision log | SKIP_ALREADY_PRESENT |
| `172dba6` | Add readiness cross-reference map | SKIP_ALREADY_PRESENT |
| `523870c` | Add operations index | SKIP_ALREADY_PRESENT |

### Tests

| Commit | Purpose | Initial action |
| --- | --- | --- |
| `bf4577a` | Add Phase 54 pilot safety controls test | SALVAGE_FILES_ONLY |
| `d4eee30` | Add Phase 54 pilot safety compatibility surfaces | SKIP_SUPERSEDED |
| `7f262fb` | Merge Phase 54 remaining safety control fixes | REJECT_UNSAFE |
| `f04af7f` | Add Phase 54 pilot safety compatibility surfaces | SKIP_SUPERSEDED |

### Generated Or Obsolete Content

| Commit | Purpose | Initial action |
| --- | --- | --- |
| `bbdc520` | Resolve orchestrator merge with broad institutional intelligence integration | REJECT_UNSAFE |
| `caf254f` | Merge `main` into candidate branch | REJECT_UNSAFE |
| `0fae9de` | Unify cross-asset scanner and orchestrator flow | SKIP_SUPERSEDED |

## File Comparison Against Current Consolidation Branch

### Already Identical

These files require no salvage:

`backend/app/brokers/execution_boundary.py`, `backend/app/brokers/install_utils.py`, `backend/app/brokers/live_readiness_certifier.py`, `backend/app/persistence/__init__.py`, `backend/app/persistence/db.py`, `backend/app/persistence/migrations/__init__.py`, `backend/app/persistence/migrations/runner.py`, `backend/app/persistence/migrations/sql/001_sessions.sql`, `backend/app/persistence/migrations/sql/002_trades.sql`, `backend/app/persistence/migrations/sql/003_pnl_snapshots.sql`, `backend/app/persistence/repositories/__init__.py`, `backend/app/persistence/repositories/base_repository.py`, `backend/app/persistence/repositories/pnl_snapshot_repository.py`, `backend/app/persistence/repositories/session_repository.py`, `backend/app/persistence/services/__init__.py`, `backend/engine/intelligence_orchestrator.py`, `dashboard/runtime/operator_action_audit_ledger.py`, `dashboard/runtime/replay_correlation.py`, `dashboard/runtime/replay_event_envelope.py`, `dashboard/runtime/replay_timeline_builder.py`, `dashboard/runtime/runtime_event_bus.py`, `dashboard/runtime/runtime_event_inspector.py`, `dashboard/runtime/runtime_event_persistence_policy.py`, `dashboard/runtime/runtime_event_persistence_report.py`, `dashboard/runtime/runtime_event_persistence_scenario.py`, `dashboard/runtime/runtime_event_persistence_simulator.py`, `dashboard/runtime/runtime_event_storage_profiles.py`, `dashboard/runtime/trade_lifecycle_replay_sink.py`, `dashboard/runtime/trade_lifecycle_replay_viewer.py`, `dashboard/runtime/trade_lifecycle_service.py`, `dashboard/runtime/trade_replay_harness.py`, `docs/architecture/CSS_RUNTIME_EVENT_PERSISTENCE_DESIGN_2026.md`, `docs/deployment/CSS_LIVE_READINESS_CERTIFICATION_2026.md`, `docs/operations/CSS_CONTROLLED_MICRO_LIVE_PILOT_RUNBOOK_2026.md`, `docs/operations/CSS_MICRO_LIVE_PILOT_ARCHIVE_NAMING_RETENTION_POLICY_2026.md`, `docs/operations/CSS_MICRO_LIVE_PILOT_EVIDENCE_BUNDLE_MANIFEST_2026.md`, `docs/operations/CSS_MICRO_LIVE_PILOT_EVIDENCE_INDEX_2026.md`, `docs/operations/CSS_MICRO_LIVE_PILOT_INCIDENT_REVIEW_WORKSHEET_2026.md`, `docs/operations/CSS_MICRO_LIVE_PILOT_NO_GO_DECISION_LOG_2026.md`, `docs/operations/CSS_MICRO_LIVE_PILOT_OPERATIONS_INDEX_2026.md`, `docs/operations/CSS_MICRO_LIVE_PILOT_OPERATOR_DAILY_BRIEF_2026.md`, `docs/operations/CSS_MICRO_LIVE_PILOT_PACKET_PRINT_CHECKLIST_2026.md`, `docs/operations/CSS_MICRO_LIVE_PILOT_READINESS_CROSS_REFERENCE_MAP_2026.md`, `docs/operations/CSS_MICRO_LIVE_PILOT_SIGN_OFF_REGISTER_2026.md`, `docs/operations/CSS_POST_PILOT_EVIDENCE_TEMPLATE_2026.md`, `docs/ops/CSS_Repository_Reconciliation_Report_2026_05_12.md`, `docs/product/CSS_MARKET_COMPANION_APP_SPEC_2026.md`, `docs/roadmap/CSS_INSTITUTIONAL_ELEVATION_BACKLOG_2026.md`, `docs/roadmap/CSS_MASTER_ROADMAP_2026.md`.

### Different From Current

These files exist in both branches. Treat the current branch as authoritative unless an isolated missing behavior is proven by tests:

`.gitignore`, `backend/app/accounting/real_balance_engine.py`, `backend/app/audit/execution_audit_ledger.py`, `backend/app/brokers/broker_bootstrap.py`, `backend/app/brokers/broker_registry.py`, `backend/app/brokers/credential_loader.py`, `backend/app/futures/futures_contract_registry.py`, `backend/app/futures/futures_execution_adapter.py`, `backend/app/futures/futures_governor.py`, `backend/app/options/options_contract_registry.py`, `backend/app/options/options_execution_adapter.py`, `backend/app/options/options_governor.py`, `backend/app/orchestration/cross_asset_execution_orchestrator.py`, `backend/app/persistence/repositories/trade_repository.py`, `backend/app/persistence/services/broker_reconciliation_service.py`, `backend/app/persistence/services/persistence_service.py`, `backend/app/persistence/services/pnl_runtime_service.py`, `backend/app/persistence/services/session_runtime_service.py`, `backend/app/persistence/services/trade_runtime_service.py`, `backend/app/risk/capital_allocation_governor.py`, `backend/app/risk/portfolio_governor.py`, `backend/app/risk/unified_risk_execution_gate.py`, `backend/broker/coinbase_adapter.py`, `backend/brokers/ibkr/ibkr_adapter.py`, `backend/brokers/ibkr/ibkr_runtime_manager.py`, `backend/intelligence/trade_decision_orchestrator.py`, `dashboard/auth/css_sign_on.py`, `dashboard/auth/css_sign_on_smoke_test.py`, `dashboard/mobile/mobile_app.py`, `dashboard/mobile/mobile_smoke_test.py`, `dashboard/runtime/api_bridge.py`, `dashboard/runtime/audit_trail_viewer.py`, `dashboard/runtime/broker_balance_reconciliation.py`, `dashboard/runtime/frontend_contract.py`, `dashboard/runtime/ws_bridge.py`, `dashboard/web/web_app.py`, `dashboard/web/web_smoke_test.py`, `docs/governance/CSS_IMPLEMENTATION_TRACKER_2026.md`, `engine/brokers/capabilities.py`, `scripts/css_live_dashboard.py`, `tests/dashboard/test_audit_trail_viewer.py`, `tests/dashboard/test_frontend_payloads.py`, `tests/dashboard/test_trade_replay_harness.py`, `ui/backend/app/dashboard_state_router.py`.

### Missing In Current

These candidate files are absent from current consolidation branch and are the only file-level salvage pool:

`backend/app/audit/persistent_execution_journal.py`, `backend/intelligence/live_dashboard_trade_controls.py`, `dashboard/auth/persistent_session_store.py`, `dashboard/auth/user_store_db.py`, `dashboard/runtime/alerting_layer.py`, `dashboard/runtime/broker_adapter_conformance.py`, `dashboard/runtime/broker_live_dry_run_certification.py`, `dashboard/runtime/coinbase_micro_live_dry_run_probe.py`, `dashboard/runtime/deployment_profiles.py`, `dashboard/runtime/evidence_hashing.py`, `dashboard/runtime/evidence_notarization_readiness.py`, `dashboard/runtime/evidence_signature_readiness.py`, `dashboard/runtime/evidence_verification_checklist.py`, `dashboard/runtime/evidence_verification_checklist_export.py`, `dashboard/runtime/evidence_verification_readiness.py`, `dashboard/runtime/live_credential_attestation.py`, `dashboard/runtime/live_dashboard_state.py`, `dashboard/runtime/micro_live_broker_readiness_confirmation.py`, `dashboard/runtime/micro_live_manual_pilot_checklist.py`, `dashboard/runtime/micro_live_operator_approval_gate.py`, `dashboard/runtime/micro_live_pilot_order_intent.py`, `dashboard/runtime/micro_live_pilot_readiness.py`, `dashboard/runtime/micro_live_pre_pilot_go_no_go.py`, `dashboard/runtime/post_pilot_archive_manifest_hash.py`, `dashboard/runtime/post_pilot_evidence_archive_export.py`, `dashboard/runtime/post_pilot_reconciliation_workflow.py`, `dashboard/runtime/runtime_event_persistence_checklist.py`, `dashboard/runtime/runtime_event_persistence_checklist_export.py`, `dashboard/web/static/css/governance.css`, `scripts/pcnrass_release_check.py`, `tests/dashboard/test_broker_adapter_conformance.py`, `tests/dashboard/test_broker_live_dry_run_certification.py`, `tests/dashboard/test_coinbase_micro_live_dry_run_probe.py`, `tests/dashboard/test_evidence_hashing.py`, `tests/dashboard/test_evidence_notarization_readiness.py`, `tests/dashboard/test_evidence_signature_readiness.py`, `tests/dashboard/test_evidence_verification_checklist.py`, `tests/dashboard/test_evidence_verification_checklist_export.py`, `tests/dashboard/test_evidence_verification_readiness.py`, `tests/dashboard/test_live_credential_attestation.py`, `tests/dashboard/test_micro_live_broker_readiness_confirmation.py`, `tests/dashboard/test_micro_live_manual_pilot_checklist.py`, `tests/dashboard/test_micro_live_operator_approval_gate.py`, `tests/dashboard/test_micro_live_pilot_order_intent.py`, `tests/dashboard/test_micro_live_pilot_readiness.py`, `tests/dashboard/test_micro_live_pre_pilot_go_no_go.py`, `tests/dashboard/test_operator_action_audit_ledger.py`, `tests/dashboard/test_phase54_pilot_safety_controls.py`, `tests/dashboard/test_post_pilot_archive_manifest_hash.py`, `tests/dashboard/test_post_pilot_evidence_archive_export.py`, `tests/dashboard/test_post_pilot_reconciliation_workflow.py`, `tests/dashboard/test_replay_correlation_lineage.py`, `tests/dashboard/test_runtime_event_bus.py`, `tests/dashboard/test_runtime_event_inspector.py`, `tests/dashboard/test_runtime_event_persistence_checklist.py`, `tests/dashboard/test_runtime_event_persistence_checklist_export.py`, `tests/dashboard/test_runtime_event_persistence_policy.py`, `tests/dashboard/test_runtime_event_persistence_report.py`, `tests/dashboard/test_runtime_event_persistence_scenario.py`, `tests/dashboard/test_runtime_event_persistence_sim_ui.py`, `tests/dashboard/test_runtime_event_persistence_simulator.py`, `tests/dashboard/test_trade_lifecycle_replay_ui.py`, `tests/dashboard/test_trade_lifecycle_replay_viewer.py`, `tests/engine/test_live_readiness_certifier.py`.

## Salvage Candidate Decisions

| Candidate commit SHA | Affected files | Purpose | Current equivalent implementation | Duplication risk | Regression risk | Recommended action | Required tests | Likely conflicts | Rollback boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `72864d3`-`8515942` | `backend/app/persistence/*` core DB, migrations, repositories | Durable session/trade/PnL persistence foundation | Current branch already contains identical DB, migrations, base/session/PnL repositories and services package | Low | Low | SKIP_ALREADY_PRESENT | Existing persistence tests only if touched | None | No change |
| `3b5aa74`, `524472b`, `2c0f4ec`, `892fb5b`, `61026ed` | `trade_repository.py`, persistence service and runtime services | Persistence services and trade query helpers | Current branch contains newer persistence with legal acceptance repository, migration `004_legal_acceptances.sql`, lifecycle adapters, and `get_all_session_trades` already present in current diff direction | Medium | Medium | SKIP_SUPERSEDED | `pytest tests/test_asset_lifecycle_integration.py tests/test_pnl_snapshot_persistence_contract.py` | Service constructor and migration ordering | No change |
| `6789459`, `97ebffb`, `8f71b21`, `2d8d285` | `backend/app/futures/*`, `backend/app/options/*`, `backend/app/orchestration/cross_asset_execution_orchestrator.py` | Dry-run options/futures governance and cross-asset orchestration | Current branch has these files plus lifecycle adapters; differences are mostly UTF-8 BOM removal and later additions | Medium | High if wholesale merged | SKIP_SUPERSEDED | `pytest tests/test_options_lifecycle.py tests/test_futures_lifecycle.py tests/test_asset_lifecycle_integration.py` | Execution/orchestration authority paths | No change |
| `bbda834` | `backend/app/audit/persistent_execution_journal.py` | Append-only JSONL execution journal; no broker calls or execution authority | Current has in-memory `ExecutionAuditLedger`; no durable journal equivalent found | Medium | Medium because it writes to `artifacts/audit/execution_journal.jsonl` during runtime | MANUAL_RECONSTRUCTION | New unit tests for append/read/sanitization plus `pytest tests/dashboard/test_audit_trail_viewer.py` | Audit path policy, artifact directory policy, metadata redaction | Add as isolated utility first; no orchestration integration in first pass |
| `676950e` | `dashboard/runtime/evidence_hashing.py`, `tests/dashboard/test_evidence_hashing.py` | Immutable evidence hash package with no order placement and sensitive-key checks | No current file equivalent; governance docs reference evidence practices but not this runtime helper | Low | Low if ported without API/web wiring | SALVAGE_FILES_ONLY | `pytest tests/dashboard/test_evidence_hashing.py` | None if helper/test only | Revert added helper/test |
| `e1407d7`, `38acdad`, `05e2072`, `51a3735`, `51389af`, `f3d4b94` | Evidence notarization/signature/verification/checklist modules and tests | Evidence packet readiness and verification surfaces | No current file equivalents; current branch has broader dashboard runtime but lacks these modules | Medium | Medium if web/API integration is ported directly | SALVAGE_FILES_ONLY | Corresponding `tests/dashboard/test_evidence_*` tests | `dashboard/runtime/api_bridge.py`, `dashboard/web/web_app.py`, `tests/dashboard/test_frontend_payloads.py` | Port helpers/tests first; defer UI/API wiring |
| `760de5a`, `a64f2d9`, `ce17be2`, `8b0b20a`, `d71ed7c`, `39135c5`, `7d6c5ba` | Micro-live readiness/order-intent/dry-run probe/operator approval/broker readiness/go-no-go/checklist modules and tests | Non-executing micro-live readiness evidence stack | Current branch has newer broker readiness and live-readiness docs but lacks these specific runtime evidence modules | Medium | Medium-high due live-mode terminology; code asserts no order placement but must be revalidated | SALVAGE_FILES_ONLY | Corresponding `tests/dashboard/test_micro_live_*`, `test_coinbase_micro_live_dry_run_probe.py` | API/web dashboard surfaces and broker naming | Port modules/tests only; no broker execution wiring |
| `2aef8f6`, `86d5495`, `37876df` | Post-pilot reconciliation/export/archive manifest modules and tests | Post-pilot evidence reconciliation/export/hash tooling | No current file equivalents found | Low | Medium if connected to dashboard state prematurely | SALVAGE_FILES_ONLY | Corresponding `tests/dashboard/test_post_pilot_*` tests | API/web integration | Port modules/tests first |
| `293f57e`, `d8efba4` | `runtime_event_persistence_checklist*` modules and tests | Runtime event persistence checklist/export | Core event persistence policy/report/simulator already identical; checklist modules are missing | Low | Low | SALVAGE_FILES_ONLY | `pytest tests/dashboard/test_runtime_event_persistence_checklist*.py` | None if helper/test only | Revert helper/test |
| `bf4577a` | `tests/dashboard/test_phase54_pilot_safety_controls.py` | Pilot safety controls regression test | No current test file equivalent found; implementation surfaces differ | Medium | Low if test is ported after confirming current API names | SALVAGE_FILES_ONLY | That test plus dependent dashboard tests | API names may differ | Test-only port; no runtime changes |
| `e6ab6cd` | `backend/brokers/ibkr/*`, broker bootstrap/reconciliation edits | IBKR scaffold and reconciliation | Current branch already has `backend/brokers/ibkr/*` but governance documents classify IBKR as isolated/not deployed | High | High if connected to active broker routing | SKIP_SUPERSEDED | Broker readiness tests only if touched | Broker registry and execution authority | No change |
| `e596a96` | Multi-broker live routing edits | Institutional multi-broker live execution routing | Current authority keeps derivatives live execution disabled and broker enablement controlled | High | High | REJECT_UNSAFE | N/A | Execution authority | No change |
| `bbdc520`, `caf254f`, `7f262fb`, `0fae9de` | Broad merge/orchestrator/dashboard rewrites | Large branch reconciliation and merge commits | Current branch is much newer and contains many additional systems that candidate branch would delete in two-dot comparison | Very high | Very high | REJECT_UNSAFE | N/A | No change |

## Smallest Coherent Salvage Units

Recommended order:

1. `676950e` file-level salvage: `dashboard/runtime/evidence_hashing.py` plus `tests/dashboard/test_evidence_hashing.py`.
2. `bbda834` manual reconstruction: durable execution journal utility, with a new test and no orchestration integration.
3. `293f57e` and `d8efba4` file-level salvage: runtime event persistence checklist helpers and tests.
4. Micro-live evidence modules as isolated helper/test ports only, starting with `a64f2d9` and `ce17be2` after evidence hashing is validated.
5. Post-pilot evidence modules as isolated helper/test ports only.

Exact recommended first salvage unit:

| Field | Value |
| --- | --- |
| Candidate commit SHA | `676950e` |
| Files | `dashboard/runtime/evidence_hashing.py`, `tests/dashboard/test_evidence_hashing.py` |
| Purpose | Add deterministic evidence hash-chain helper that explicitly does not authorize trading, arm execution, place orders, mutate broker state, or bypass governance. |
| Current equivalent implementation | No current runtime helper file found. Current docs and loose audit files reference evidence hashing, but no active `dashboard/runtime/evidence_hashing.py` exists. |
| Duplication risk | Low. |
| Regression risk | Low if ported without `api_bridge.py`, `web_app.py`, `.gitignore`, or tracker edits. |
| Recommended action | SALVAGE_FILES_ONLY |
| Required tests | `python -m pytest tests/dashboard/test_evidence_hashing.py -q`; then `python -m pytest tests/dashboard/test_frontend_payloads.py -q` only if later API/frontend wiring is added. |
| Likely conflicts | None for helper/test-only port; conflicts expected only if web/API/tracker changes are included. |
| Rollback boundary | Revert the helper and test file only. No broker, execution, or runtime authority files should be touched in the first salvage unit. |

## Required Validation Commands

Use the repository Python executable when available; in this environment the local `.venv` Python launcher was not usable during the audit, so command paths may need adjustment before execution.

```powershell
git status --short --branch
git diff --check
python -m pytest tests/dashboard/test_evidence_hashing.py -q
python -m pytest tests/dashboard/test_runtime_event_persistence_checklist.py tests/dashboard/test_runtime_event_persistence_checklist_export.py -q
python -m pytest tests/dashboard/test_micro_live_pilot_order_intent.py tests/dashboard/test_coinbase_micro_live_dry_run_probe.py -q
python -m pytest tests/dashboard/test_post_pilot_reconciliation_workflow.py tests/dashboard/test_post_pilot_evidence_archive_export.py tests/dashboard/test_post_pilot_archive_manifest_hash.py -q
python -m pytest tests/test_options_lifecycle.py tests/test_futures_lifecycle.py tests/test_asset_lifecycle_integration.py -q
```

## Stop Boundary

This review stops before integration. No branch merge, cherry-pick, runtime source edit, broker edit, execution logic edit, CSS restart, deployment, Desktop update, or branch deletion is included in this stage.

## Salvage Unit 1 Completion Record

Completed on: 2026-07-14

Working branch: `css-unified-consolidation-2026-07-13`

Baseline before salvage: `c2c4d588df2710b23548e49bffe0b9aa337639e9`

Source branch: `phase1-persistence-foundation`

Source commit reviewed: `676950e`

Files salvaged:

- `dashboard/runtime/evidence_hashing.py`
- `tests/dashboard/test_evidence_hashing.py`

The full source commit was not cherry-picked because `676950e` also changed `.gitignore`, `dashboard/runtime/api_bridge.py`, `dashboard/web/web_app.py`, `dashboard/web/web_smoke_test.py`, `docs/governance/CSS_IMPLEMENTATION_TRACKER_2026.md`, and `tests/dashboard/test_frontend_payloads.py`. Those companion changes were outside the approved salvage boundary and would have modified API, web dashboard, governance tracker, and frontend test surfaces.

Implementation review:

- Uses standard SHA-256 via `hashlib.sha256`.
- Encodes canonical hash input explicitly with UTF-8.
- Uses canonical JSON serialization with `sort_keys=True`, compact separators, and ASCII-safe output.
- Keeps generated timestamps as metadata only; timestamps are not included in the hashed canonical payload.
- Handles mappings, lists, tuples, scalars, `Decimal`, `datetime`, `Path`, strings, and `None` through `_json_safe`.
- Redacts sensitive key names and sensitive string markers before hashing/output.
- Contains no broker imports, execution imports, credential reads, environment reads, database access, machine-specific paths, runtime process start, broker mutation, or live-trading state mutation.
- Declares read-only safety metadata: no broker calls, no order placement, no account mutation, no approval grant endpoint, no trading arm, and no persistence activation.

Compatibility changes made:

- `dashboard/runtime/evidence_hashing.py`: sorted mapping source keys by `str(key)` in `_iter_sources` so mixed key types cannot break deterministic source ordering.
- `tests/dashboard/test_evidence_hashing.py`: removed tests that depended on unapproved companion API/web changes from `676950e`; kept the dedicated module tests and added deterministic nested-value coverage for lists, tuples, scalars, nested mappings, and `None`.

Validation performed:

```powershell
.\.venv\Scripts\python.exe -m py_compile dashboard/runtime/evidence_hashing.py tests/dashboard/test_evidence_hashing.py
```

Result: passed. The first sandboxed attempt failed because the venv pointed at an access-denied `Python314` executable; the retried approved command passed.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/dashboard/test_evidence_hashing.py -q
```

Result: `7 passed in 1.38s`.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_options_lifecycle.py tests/test_futures_lifecycle.py tests/test_asset_lifecycle_integration.py -q
```

Result: `13 passed in 6.88s`.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_phase163b3j_broker_state_authority.py -q
```

Result: `5 passed in 3.72s`. The file existed. The first sandboxed attempt hit the same access-denied interpreter path; the retried approved command passed.

Rollback boundary:

- Revert `dashboard/runtime/evidence_hashing.py`.
- Revert `tests/dashboard/test_evidence_hashing.py`.
- Revert this completion record in `docs/governance/PHASE1_PERSISTENCE_FOUNDATION_SALVAGE_PLAN.md`.

No broker adapters, execution routing, live-trading controls, credentials, `.env`, PEM files, API keys, runtime state, databases, Desktop files, generated artifacts, branch history, or deployment/runtime processes were modified.
