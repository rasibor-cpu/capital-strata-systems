# CSS Options Completion Matrix

Audit generated: 2026-07-14

Evidence base: current authoritative branch `css-evening-consolidation-2026-06-09` at `33f814d82882c91a09694c4fd8644e21b0786d35`.

Status terms:

- `COMPLETE`: implementation exists on the authoritative branch and has direct test or runtime wiring evidence.
- `PARTIAL`: implementation exists but is bounded, simulated, non-live, or missing full strategy/broker coverage.
- `PLACEHOLDER`: repo evidence explicitly describes a scaffold, disabled mode, future plug-in, or spec-only surface.
- `NOT PRESENT`: no implementation evidence found in searched files.

## Options Inventory

| Area | Status | Repository evidence | Notes |
| --- | --- | --- | --- |
| execution | PARTIAL | `backend/app/options/options_execution_adapter.py:30` says dry-run only; `backend/app/options/options_execution_adapter.py:31` says no live order placement; `backend/app/options/options_execution_adapter.py:48` implements `execute_options_order`; `backend/app/orchestration/cross_asset_execution_orchestrator.py` routes OPTIONS through the dry-run adapter | Simulated/governed execution exists. Live broker order placement is not implemented. |
| strategy engine | PARTIAL | `backend/options/options_strategy_engine.py:10-17` lists live enabled long call, long put, call debit spread, put debit spread and scaffolded covered call/cash-secured put; `backend/options/option_payoff_engine.py:9-18` calculates payoffs for long calls/puts and debit spreads | Core single-leg and debit-spread logic exists. Income strategies are scaffolded only. |
| Greeks | COMPLETE | `backend/trading/greeks_engine.py:23` defines `GreeksEngine`; `backend/trading/greeks_engine.py:78` implements calculate; dashboard exposes portfolio Greeks at `dashboard/web/web_app.py:529-548`; tests cover data model/dashboard/aggregation in `tests/test_options_greeks_data_model.py`, `tests/test_options_greeks_dashboard.py`, and `tests/test_portfolio_greeks_aggregation.py` | Broker-neutral Greeks calculation and dashboard aggregation are present. |
| spreads | PARTIAL | `backend/options/options_strategy_engine.py:116` builds call debit spreads; put debit spreads are also implemented in the same engine; `backend/options/option_payoff_engine.py:27` handles call debit spread payoff | Debit spreads exist. No evidence of credit spreads, vertical spread order routing, or broker execution. |
| covered calls | PLACEHOLDER | `backend/options/options_strategy_engine.py:15-17` marks `COVERED_CALL` as scaffolded; `backend/options/options_intelligence_engine.py:43` names `COVERED_CALL` | Mentioned/scaffolded only; no builder, position lifecycle, assignment handling, or execution path found. |
| cash secured puts | PLACEHOLDER | `backend/options/options_strategy_engine.py:15-17` marks `CASH_SECURED_PUT` as scaffolded; `backend/options/options_intelligence_engine.py:44` names `CASH_SECURED_PUT` | Mentioned/scaffolded only; no collateral reservation or assignment-aware lifecycle found. |
| Wheel | NOT PRESENT | Searches for Wheel/WHEEL found no implemented options module or tests | No repository evidence of Wheel strategy implementation. |
| assignment | NOT PRESENT | Searches found governance/risk mentions of assignment, but no options assignment engine, assignment event model, or tests | Assignment risk is documented in governance, not implemented as options lifecycle behavior. |
| rolling | PARTIAL | `backend/learning/rolling_reliability.py` and `tests/test_phase139a_rolling_reliability.py` exist, and futures universe has roll policy fields; no options roll-order or roll-position implementation was found | Reliability/learning support exists, but options rolling execution/lifecycle is not implemented. |
| dashboard | COMPLETE | Web dashboard exposes portfolio Greeks and options exposure fields at `dashboard/web/web_app.py:529-548`; mobile ticket UI includes asset class `OPTIONS` at `dashboard/mobile/mobile_app.py:2989`; tests cover Greeks dashboard and strategy classification | Display and classification surfaces exist. Dashboard does not imply live execution approval. |
| broker integration | PLACEHOLDER | `backend/scanner/options_chain_adapter.py:71` says real broker APIs can be plugged in later; execution adapter says no broker calls/no live order placement | Broker-live options integration is not implemented. |
| tests | COMPLETE | `tests/test_options_lifecycle.py`, `tests/test_options_strategy_classification.py`, `tests/test_options_greeks_data_model.py`, `tests/test_options_greeks_dashboard.py`, `tests/test_portfolio_greeks_aggregation.py` | Tests exist for lifecycle normalization, dashboard Greeks, strategy classification, and Greek aggregation. They were inventoried, not executed during this audit. |

## Missing Work

- Live options broker adapter.
- Real options order placement.
- Covered call strategy builder and lifecycle.
- Cash-secured put strategy builder, collateral reservation, and lifecycle.
- Wheel strategy workflow.
- Assignment/exercise event handling.
- Options rolling order/lifecycle implementation.
- Credit spread coverage.
- Broker-sourced options chain integration beyond adapter scaffolding.

## Merge Recommendations For Options Work

- Do not merge old options branches wholesale.
- Review `phase1-persistence-foundation` first for current `backend/app/options/*` ancestry, tests, and cross-asset orchestrator history.
- Treat `origin/feature/options-*-spec` branches as planning/spec branches unless a specific missing spec is required.
- Treat `audit-options` and `origin/feature/options-sandbox-phase1` as duplicates of the same early sandbox work.
- Any future options consolidation should preserve the current dry-run/live-disabled safety boundary until a live broker adapter and tests are deliberately added.
