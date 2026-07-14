# CSS Futures Completion Matrix

Audit generated: 2026-07-14

Evidence base: current authoritative branch `css-evening-consolidation-2026-06-09` at `33f814d82882c91a09694c4fd8644e21b0786d35`.

Status terms:

- `COMPLETE`: implementation exists on the authoritative branch and has direct test or runtime wiring evidence.
- `PARTIAL`: implementation exists but is bounded, simulated, non-live, or missing full strategy/broker coverage.
- `PLACEHOLDER`: repo evidence explicitly describes a scaffold, disabled mode, future plug-in, or spec-only surface.
- `NOT PRESENT`: no implementation evidence found in searched files.

## Futures Inventory

| Area | Status | Repository evidence | Notes |
| --- | --- | --- | --- |
| execution | PARTIAL | `backend/app/futures/futures_execution_adapter.py:30` says dry-run only; `backend/app/futures/futures_execution_adapter.py:31` says no live order placement; `backend/app/futures/futures_execution_adapter.py:50` implements `execute_futures_order`; `engine/derivatives/futures_trade_adapter.py` converts futures requests into execution payloads | Simulated/governed execution exists. Live broker futures execution is not implemented. |
| lifecycle | COMPLETE | `backend/app/futures/futures_lifecycle_adapter.py:11` defines `FuturesLifecycleAdapter`; `tests/test_futures_lifecycle.py:22`, `:60`, and `:91` cover normalization, paper persistence, duplicate prevention, and fail-closed behavior | Canonical open/close payload normalization and persistence are implemented. |
| contract intelligence | COMPLETE | `backend/trading/futures_contract.py:74` defines `CanonicalFuturesContract`; `backend/trading/futures_contract.py:87` includes `rollover_date`; `backend/trading/canonical_futures_repository.py` normalizes/searches futures contracts; `backend/app/futures/futures_contract_registry.py` defines supported futures contracts | Contract metadata, registry, and canonical models exist. |
| dashboard | PARTIAL | Web dashboard supports asset-class rollups and exposure display; mobile UI includes `FUTURES` asset class at `dashboard/mobile/mobile_app.py:2990`; summary contract has `futures_exposure` and `futures_trades` | Dashboard visibility exists. No dedicated futures execution dashboard with broker-live controls was found. |
| orchestration | PARTIAL | `backend/app/orchestration/cross_asset_execution_orchestrator.py` routes FUTURES through `FuturesExecutionAdapter`; `backend/execution/unified_execution_pipeline.py:48` supports FUTURES as an asset class | Cross-asset routing exists, but the futures route remains dry-run/live-disabled. |
| risk | COMPLETE | `backend/app/futures/futures_governor.py:23` defines `FuturesGovernor`; `backend/app/risk/futures_contract_specs.py:112` implements `calculate_futures_risk`; `backend/app/brokers/futures_sim_adapter.py:19` simulates trades with allocation enforcement; `backend/app/risk/futures_position_manager.py:25` manages positions | Risk calculation, quantity/margin class gating, simulated allocation enforcement, and position risk tracking exist. |
| PnL | PARTIAL | `backend/app/risk/futures_position_manager.py` computes unrealized and realized PnL on close; dashboard summary contracts include futures exposure/trade counters; canonical lifecycle records realized PnL | Futures PnL exists in position/lifecycle paths, but no futures-specific broker reconciliation or full dashboard PnL module was found. |
| tests | COMPLETE | `tests/test_futures_lifecycle.py`, `tests/test_asset_lifecycle_integration.py`, `tests/test_canonical_trade_lifecycle.py`, `tests/test_broker_margin_contract.py` | Tests exist for lifecycle, asset-class integration, canonical lifecycle, and margin contract behavior. They were inventoried, not executed during this audit. |

## Missing Work

- Live futures broker adapter.
- Real futures order placement.
- Broker-live futures margin/reconciliation loop.
- Dedicated futures dashboard execution controls.
- Futures broker fill ingestion.
- Full futures PnL reconciliation against broker statements.

## Merge Recommendations For Futures Work

- Preserve the current dry-run/live-disabled futures boundary.
- Review `phase1-persistence-foundation` for futures adapter, governor, contract registry, and orchestration ancestry.
- Review `PRE_MERGE_SAFETY_2026_05_20` for persistence/reconciliation support that may help futures lifecycle durability.
- Treat `origin/feature/futures-orchestrator-integration-spec` as already integrated into the authoritative branch by ancestry.
- Do not merge older dashboard/PnL recovery branches wholesale just to obtain futures behavior; port only confirmed missing functions after tests.
