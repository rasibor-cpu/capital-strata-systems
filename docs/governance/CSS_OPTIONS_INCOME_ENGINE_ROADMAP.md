# CSS Options Income Engine Roadmap

Audit date: 2026-07-13

Branch: `css-unified-consolidation-2026-07-13`

Baseline reviewed: `8fb62f19c81650f7975edcb0ee9647b3d8d5f3df`

This roadmap starts from the consolidated branch only. It does not rely on historical branches.

## Roadmap Principles

- Keep live options execution disabled until a separate production certification milestone approves it.
- Build income capability through paper-safe, independently testable phases.
- Preserve PCNRASS, MAEP, broker-state authority, authentication, evidence, and execution-governance controls.
- Treat broker state as authority for live readiness, never as an inferred side effect.
- Keep evidence, journal, and runtime events as audit surfaces; they must not alter trading decisions.

## Completed Foundations

| Foundation | Repository evidence | Current readiness |
| --- | --- | --- |
| Canonical option contract model | `backend/trading/option_contract.py`; `backend/trading/canonical_options_repository.py`; `tests/test_canonical_derivatives_foundation.py` | Complete pending production certification |
| Greeks engine and dashboard aggregation | `backend/trading/greeks_engine.py`; `scripts/css_live_dashboard.py`; `dashboard/runtime/frontend_contract.py`; `tests/test_options_greeks_data_model.py`; `tests/test_options_greeks_dashboard.py`; `tests/test_portfolio_greeks_aggregation.py` | Complete pending certified data/model validation |
| Paper-safe lifecycle and execution foundation | `backend/app/options/options_lifecycle_adapter.py`; `backend/app/options/options_execution_adapter.py`; `backend/execution/unified_execution_pipeline.py`; `tests/test_options_lifecycle.py`; `tests/test_unified_execution_pipeline.py` | Partial, dry-run only |
| Directional and debit-spread strategy math | `backend/options/options_strategy_engine.py`; `backend/options/option_payoff_engine.py`; `backend/options/option_risk_profile_engine.py` | Partial, no income strategy lifecycle |
| Dashboard strategy classification | `scripts/css_live_dashboard.py`; `tests/test_options_strategy_classification.py` | Display/data-model only |
| Governance and consolidation evidence | Existing options specs and `docs/architecture/CSS_OPTIONS_INCOME_ENGINE_COMPLETION_MATRIX.md` | Ready for planning use |

## Phase OI-002: Income Strategy Domain Model

Objective: implement paper-safe covered-call and cash-secured-put domain models without broker routing.

Affected modules:

- `backend/options/options_strategy_engine.py`
- `backend/options/option_payoff_engine.py`
- `backend/options/option_risk_profile_engine.py`
- New focused option-income model module if needed.

Expected tests:

- Covered-call builder rejects missing/insufficient underlying share coverage.
- Cash-secured-put builder rejects insufficient cash collateral.
- Payoff calculations cover premium received, max profit, max loss, breakeven, collateral, and assignment exposure.
- Malformed legs fail closed.
- Existing long-call, long-put, and debit-spread tests remain unchanged.

Dependencies:

- Canonical option contract model.
- Current strategy/payoff/risk engines.
- Options risk-governor specification.

Validation:

- Unit tests for covered calls and cash-secured puts.
- Regression tests for existing options lifecycle, Greeks, and unified execution pipeline.
- Confirm no broker, execution routing, authentication, or live-trading behavior changes.

## Phase OI-003: Income Opportunity Scan and Contract Selection

Objective: extend opportunity selection for income strategies using repository-native option candidate fields.

Affected modules:

- `backend/options/options_intelligence_engine.py`
- `backend/trading/canonical_options_repository.py`
- `backend/scanner/options_chain_adapter.py` only if test fixtures need deterministic paper data.

Expected tests:

- Covered-call scan ranks calls by DTE, delta, premium, spread, volume, open interest, and moneyness.
- Cash-secured-put scan ranks puts by DTE, delta, premium, spread, volume, open interest, and collateral efficiency.
- Scanner rejects non-tradable/mock rows for live paths.
- Deterministic fixtures avoid random option-chain behavior.

Dependencies:

- Phase OI-002 strategy models.
- Canonical option contract model.

Validation:

- Deterministic unit tests for scan/rank behavior.
- Regression on canonical derivatives and dashboard metadata tests.

## Phase OI-004: Paper Income Lifecycle

Objective: add short-premium lifecycle states for paper covered calls and cash-secured puts.

Affected modules:

- `backend/options/options_position_manager.py`
- `backend/app/options/options_lifecycle_adapter.py`
- New income lifecycle module if needed.

Expected tests:

- Open, mark, close, expire-worthless, assignment-pending, assigned, and rejected states.
- Lifecycle records preserve strategy, collateral, premium, expiry, and assignment exposure.
- Duplicate and malformed records fail closed.
- No live execution mode accepted.

Dependencies:

- Phase OI-002.
- Phase OI-003 for selected contracts.

Validation:

- Options lifecycle regression.
- Canonical trade lifecycle regression.
- Asset lifecycle integration regression.

## Phase OI-005: Options Income Risk Governor

Objective: implement options-specific paper risk controls from `docs/options_risk_governor_spec.md`.

Affected modules:

- New `backend/app/options/options_risk_governor.py` or compatible current architecture location.
- `backend/app/options/options_governor.py` only for additive integration.
- Portfolio/capital governor integration only after isolated tests pass.

Expected tests:

- Max premium at risk per trade.
- Max total options premium at risk.
- Max open income positions.
- Per-symbol concentration.
- Near-expiry exposure cap.
- Daily options loss stop.
- Fail-closed behavior for missing equity/collateral inputs.

Dependencies:

- Phase OI-004 lifecycle state.
- Existing portfolio and capital governors.

Validation:

- Risk governor unit tests.
- Portfolio governor and capital allocation regression.
- Broker-state authority regression to confirm no authority bypass.

## Phase OI-006: Evidence, Journal, and Runtime Event Integration

Objective: record option income decisions and lifecycle events as audit evidence without changing decisions.

Affected modules:

- `dashboard/runtime/evidence_hashing.py`
- `backend/app/audit/persistent_execution_journal.py`
- Runtime event normalization modules under `dashboard/runtime/`
- Options lifecycle and orchestration adapters only for append-only audit writes.

Expected tests:

- Deterministic evidence hashes for option decision payloads.
- Journal entries for income open/close/expiry/assignment events.
- Runtime events include correlation IDs, source, severity, category, and metadata.
- Audit failures do not create live orders or alter broker state.

Dependencies:

- Phase OI-004 lifecycle event taxonomy.
- Existing evidence hashing, execution journal, and runtime event normalization foundations.

Validation:

- Evidence hashing tests.
- Persistent execution journal tests.
- Runtime event normalization tests.
- Options lifecycle regression.

## Phase OI-007: Dashboard and Reporting for Options Income

Objective: expose read-only income engine state in dashboard/reporting surfaces.

Affected modules:

- `dashboard/runtime/frontend_contract.py`
- `dashboard/web/web_app.py`
- `dashboard/mobile/mobile_app.py`
- `dashboard/summaries/summary_contract.py`
- Existing dashboard tests.

Expected tests:

- Covered-call and cash-secured-put positions render strategy, collateral, premium, DTE, assignment exposure, and Greeks.
- Portfolio income summary separates premium received, realized PnL, unrealized PnL, collateral, and assignment risk.
- Missing data renders as unavailable instead of inferred.
- No dashboard layer becomes execution authority.

Dependencies:

- Phase OI-004 lifecycle state.
- Phase OI-006 evidence/event payloads.

Validation:

- Dashboard payload tests.
- Frontend contract tests.
- Mobile opportunity and trade-tab tests.

## Phase OI-008: Paper Broker-State Reconciliation

Objective: reconcile paper option positions with broker-state authority interfaces without placing live orders.

Affected modules:

- Broker-state authority interfaces.
- Options lifecycle adapter.
- Options risk governor.

Expected tests:

- Broker-state authority remains the only source for account/position readiness.
- Paper reconciliation handles missing option approval level, missing buying power, insufficient collateral, stale positions, and conflicting local state.
- No live broker calls are introduced.

Dependencies:

- Phase OI-005 risk governor.
- Phase OI-006 audit evidence.

Validation:

- Broker-state authority tests.
- Broker readiness and capability payload tests.
- Options lifecycle regression.

## Phase OI-009: Production Certification Package

Objective: assemble the certification evidence required before any live options capability is considered.

Affected modules:

- Governance docs.
- Certification/reporting modules.
- Read-only evidence export surfaces.

Expected tests:

- Certification blockers for missing broker chain authority, missing option approval level, missing assignment handling, missing collateral verification, or missing journal evidence.
- Read-only export packages include strategy decisions, risk approvals, lifecycle events, evidence hashes, and runtime event summaries.

Dependencies:

- Phases OI-002 through OI-008.

Validation:

- Certification test suite.
- Evidence export tests.
- Full targeted options regression suite.
- Explicit manual approval before any live-trading change.

## Advanced Phases

| Phase | Objective | Prerequisites |
| --- | --- | --- |
| OI-A1 Credit spreads | Add defined-risk short vertical spreads | Income lifecycle, collateral, assignment, and risk governor complete |
| OI-A2 Iron condors | Add multi-leg neutral income strategy | Credit spreads and multi-leg lifecycle complete |
| OI-A3 Butterflies | Add limited-risk multi-leg structures | Multi-leg pricing/reporting complete |
| OI-A4 Calendars and diagonals | Add term-structure strategies | Expiration, rolling, and IV term structure complete |
| OI-A5 Volatility analytics | Add IV rank, IV percentile, skew, and term-structure ranking | Certified market-data authority |
| OI-A6 Portfolio hedging | Add portfolio Greeks hedge recommendations | Certified Greeks aggregation and risk governance |

## Merge Readiness Criteria for the Options Income Engine

Before any options income work is merged into the main development line:

- All affected modules have deterministic unit tests.
- Existing options lifecycle, Greeks, dashboard, canonical derivatives, unified execution, broker-state authority, and evidence tests pass.
- No live options execution path is enabled.
- Broker adapters remain unchanged unless the milestone explicitly certifies broker integration.
- Evidence and journal integration is append-only and non-authoritative.
- Dashboard/reporting remains read-only.
- Governance docs identify certification blockers and rollback boundaries.

## Recommended First Implementation Phase

Begin with Phase OI-002: Income Strategy Domain Model.

Rationale:

- It directly addresses the largest product gap: covered calls and cash-secured puts are placeholders while the mission is an Options Income Engine.
- It can be implemented without broker changes, execution routing changes, Desktop changes, or live-trading behavior changes.
- It reuses the current strategy, payoff, risk-profile, canonical contract, and test patterns.
- It creates the domain foundation needed for assignment, rolling, collateral, dashboard, evidence, and certification phases.
