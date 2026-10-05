# Post-OV-002 integration specification (design only)

**Status: design only. Nothing in this document is implemented.** No file it names was modified in this tranche.
OV-002, port 8765, the frozen candidate, its runtime configuration and its execution path are untouched. This work
starts only after OV-002 completes and the owner approves a change window.

All references were read (not changed) at commit `89056d7` on 2026-10-05.

## Today's execution path (as found)

`scripts/css_live_dashboard.py`:
- The main loop (around line 4116) calls `approve_trade_before_register(asset_class, symbol, sig, prob)`. This is
  **R7**, the unified gate, at line 1891: `backend/governance/css_gate_dashboard_adapter.py`
  `CSSGateDashboardAdapter.approve_trade`, which wraps `backend/governance/css_unified_trade_gate.py`
  `CSSUnifiedTradeGate.approve_trade` / `_validate_candidate` / `_check_position_limits`.
- Then `_legacy_css_profitability_allows(...)` (**R14F**, line 54; threshold from
  `_legacy_css_profitability_threshold`, line 44; built by `scripts/build_r14f_pre_position_profitability_gate.py`).
- Then `mtm_engine.register_position(...)` (line 2758).

`engine/execution/execution_gate.py` `ExecutionGate.evaluate_trade` calls `_evaluate_anti_bleed` →
`backend/app/risk/anti_bleed_guard.py` `AntiBleedGuard.evaluate` (**AntiBleedGuard**).

Journals:
- `engine/execution_journal.py` `ExecutionJournal.record`;
- `backend/app/execution_journal.py` `record_trade_decision`, `record_order_result`, `record_global_shutdown`.

Persistence: `backend/app/persistence/` (`db.py`; `repositories/trade_repository.py` `TradeRepository.create_trade` /
`close_trade`; `services/trade_runtime_service.py`, `broker_reconciliation_service.py`, `pnl_runtime_service.py`;
SQL migrations in `migrations/sql`).

Trade warehouse: `dashboard/trade_warehouse/trade_record_contract.py` `TradeRecord`.

**Key finding.** The current loop registers **system-generated** positions from signals. There is no user Trade Card
confirmation step and no user-entered order path. Before integration, the owner must decide how these
system-originated positions are classified:
- CSS_RECOMMENDED with a system "recommendation" record per signal; or
- a fifth, internal-only `CSS_SYSTEM` source excluded from user statements; or
- out of scope for customer attribution.

Until that is decided they must not be relabelled. They stay **Origin Under Review** in customer views
(`from_legacy_closed_trades`).

## Target flow

```
Trade Card (versioned, fingerprinted, envelope) ──► user action (Confirm / edit / own order)
   │                                                      │
   ▼                                                      ▼
RecommendationRegistry.add (persisted)        OrderIntent (+ recommendation_id, version, fingerprint, via_css_workflow)
                                                          │
                                            classify_order ─► OriginLedger.record (persisted, append-only)   [1]
                                                          │
                       governance gates, unchanged and in today's order: R7 → R14F → AntiBleedGuard            [2]
                                                          │  (rejection: journal + no fill; origin record stays)
                                              broker submission (existing adapters)                         [3]
                                                          │
                     fills ─► OriginLedger.apply_fill_check ─► TradeLifecycle.apply_open_fill (lot = order)  [4]
                                                          │
                closes / partial closes ─► TradeLifecycle.apply_close_fill (lot named explicitly)            [5]
                                                          │
               realised / unrealised P&L ─► performance.segregate ─► commercial.statement                   [6]
                                                          │
                       dashboard (3 headline numbers + 4 ledgers) / history / audit export                  [7]
```

## Integration points

| # | Where | Change (additive, behind a feature flag, default off) | Constraint |
|---|---|---|---|
| 1 | Order creation, **before** R7 | Build `OrderIntent`; `classify_order`; persist the record | Classification never blocks or approves anything; it is metadata. Fail closed: if the record can't be persisted, the order isn't created |
| 2 | R7, R14F, AntiBleedGuard | **No change** to logic, thresholds or order. Pass `order_id` through so decisions can be joined to the origin record | Attribution must never influence gate outcomes; tested by comparing gate decisions with the flag on and off |
| 2a | `backend/app/execution_journal.record_trade_decision` / `record_order_result` | Add optional `order_id`, `origin`, `recommendation_id`, `recommendation_version`, `origin_policy_version` fields | Additive; existing readers ignore unknown fields |
| 2b | `engine/execution_journal.ExecutionJournal.record` | Same optional fields | Additive |
| 3 | Broker submission | None. The broker order id is mapped to `order_id` in persistence | No broker behaviour change |
| 4 | Fill handling / `broker_reconciliation_service` | On each fill: `apply_fill_check` (fill-time envelope), then `apply_open_fill`. Duplicate fill ids refused | Fill check transitions are system-only and evidenced |
| 5 | Close handling / `TradeRepository.close_trade` | Pass the lot id explicitly; a symbol-only close is refused when lots differ in origin | Partial closes book P&L to the lot |
| 6 | `pnl_runtime_service` | Expose per-lot realised/unrealised P&L; `segregate()` and `statement()` read from persistence | Combined = sum of segments, checked |
| 7 | Dashboard / history / audit | Customer view as in `frontend/trader_passport`; reviewer queue for `ORIGIN_UNDER_REVIEW` with evidence capture; export of records + transitions | Under-review results never shown as CSS or as the user's own |

## Persistence (new tables, additive migration)

- `trade_recommendations`: (recommendation_id, version) primary key; card snapshot JSON; fingerprint; created_at.
  Immutable.
- `trade_origin_records`: order_id primary key; full `AttributionRecord.to_dict()` JSON; origin; policy version and
  fingerprint. Insert-only.
- `trade_origin_transitions`: append-only (order_id, seq) with from, to, at, actor, reason, evidence.
- `position_lots`: lot_id = opening order id; symbol, side, quantities, average entry price, realised P&L.
- `lot_closes`: lot_id, closing order id, fill id (unique), quantity, price, P&L, at.
- `TradeRecord` (warehouse): add `origin: str = "ORIGIN_UNDER_REVIEW"`, `recommendation_id: str = ""`,
  `recommendation_version: int = 0`, all defaulted so existing producers still validate.
- Onboarding: move `OnboardingStore` (JSON, mode 0600) into persistence, with the same encryption and retention as
  other personal data.

## Release sequence (after OV-002)

1. Owner decisions: the TBD materiality fields, system-position classification, commercial policy.
2. Migrations in a shadow database; replay a copy of the OV-002 evidence journal through the lifecycle in read-only
   mode to check that totals reconcile.
3. Enable recording only (flag `CSS_TRADE_ORIGIN_RECORD=1`) in paper mode, with gates unchanged. Compare gate
   decisions with the flag on and off.
4. Enable the customer view on paper data, then the reviewer queue.
5. Live only after compliance sign-off and physical-device UAT. Fees only after an approved `CommercialPolicy`.

## Tests to add at integration time

- Gate parity: identical R7/R14F/AntiBleedGuard decisions with attribution on and off.
- End-to-end paper trade per origin state, through partial and final close, reconciling journal = ledger = dashboard.
- Restart safety: records and transitions survive restart; duplicate fills after restart are refused.
- Reviewer flow: resolution requires evidence; USER_INDEPENDENT is terminal.
