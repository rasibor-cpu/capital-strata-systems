# CSS v1.0.1 — Maintenance Workstream 004
## RR-003b Paper Ledger Execution Fidelity

**Programme:** CSS v1.0.1 Maintenance
**Workstream:** MW-004 / RR-003b
**Status:** IMPLEMENTED — VALIDATED — AWAITING COMMIT APPROVAL
**Workspace:** Laptop (`C:\rasib\source\capital-strata-systems`)
**Branch:** `css-v1.0.1-maintenance`
**HEAD (base, verified pre-implementation):** `5019a57452fb0cd0b1344d7a94cf22dcabec5e48`
**Date:** 2026-07-30
**Does not authorize:** live trading, OV-002, production deployment, desktop interference

---

## 1. Confirmed root cause

Mobile paper persistence hardcoded `entry_price=0.0` and stored ticket quantity as a completed fill without recording gate `scaled_notional` or a validated execution price. Orchestrator tracking stubs used the same zero-entry pattern.

**Classification:** E. Mixed (ledger persistence + missing fill/economics structure) — confirmed.

---

## 2. Execution truth source / field ownership

| Field | Authoritative source | Persisted where |
| --- | --- | --- |
| requested quantity | ticket `qty` | `trades.quantity` / economics.requested_quantity |
| filled quantity | paper synthetic full of requested qty after ALLOW; else 0 if pending | `trades.filled_quantity` |
| requested notional | ticket `amount` | economics.requested_notional |
| scaled notional | ExecutionGate `debug.scaled_notional` | economics.scaled_notional (+ gate summary in payload) |
| canonical / entry price | gate canonical price / validated ticket price | `trades.entry_price` (must be > 0) |
| execution timestamp | persist time ISO UTC | `trades.opened_at` / economics.executed_at |

**No** `qty = scaled_notional ÷ price` inference was introduced (no such contract existed).

Contracts recorded explicitly:

- `quantity_contract = requested_quantity_authoritative`
- `notional_contract = scaled_notional_authoritative_for_risk`

---

## 3. Implementation

1. New `backend/execution/paper_execution_economics.py` builds explicit economics/fill structure.
2. Mobile ALLOW path persists validated price, requested qty, filled qty, and scaled notional in `raw_payload_json.execution_economics`.
3. `TradeRuntimeService.open_trade` rejects non-positive entry prices; supports `status=open|pending|partially_filled` with filled-qty rules.
4. Orchestrator stub no longer fabricates `entry_price=0`; skips ledger write without a positive market/ticket price.
5. Close outcome `amount_traded` uses validated amount helper (fails closed on zero entry).

---

## 4. Files changed

| File | Change |
| --- | --- |
| `backend/execution/paper_execution_economics.py` | **New** economics builder |
| `backend/app/persistence/services/trade_runtime_service.py` | Price/qty validation; amount_traded helper |
| `dashboard/mobile/mobile_app.py` | Persist economics after gate ALLOW |
| `backend/intelligence/trade_decision_orchestrator.py` | No zero-entry stub opens |
| `tests/test_mw004_paper_ledger_fidelity.py` | **New** matrix |
| `docs/governance/CSS_V1_0_1_MAINTENANCE_004_PAPER_LEDGER_FIDELITY_AUDIT.md` | This record |

---

## 5. Tests added

`tests/test_mw004_paper_ledger_fidelity.py`:

- price + scaled notional persistence
- qty vs scaled notional distinction
- zero/negative price rejection
- pending non-filled persistence
- FX + crypto economics
- restart recovery via get_open_trades
- amount_traded / close path with non-zero entry

---

## 6. Validation results

| Suite | Result |
| --- | --- |
| MW-004 | **9 passed** |
| Combined: MW-003, asset lifecycle, AntiBleed, margin, RiskGovernor, live authority, PnL snapshot, MC001, mobile paper/kill-switch, orchestrator gate | **91 passed** |
| Env cleared | CSS_ENV / DEFAULT_EXECUTION_MODE / CSS_RUNTIME_MODE / ENGINE_MODE |
| CSS started | No |
| Desktop accessed | No |

---

## 7. Safety verification

- AntiBleed / RiskGovernor / margin / live authority suites unchanged and passing
- No broker adapter, threshold, or live-enablement changes
- Invalid execution prices cannot open filled trades

---

## 8. Mission Control / PnL impact

- MC foundation regression passed
- PnL snapshot persistence regression passed
- Trade ledger fidelity improved independently of snapshot equity path

---

## 9. Remaining limitations

1. Paper fill remains **synthetic full requested qty** after ALLOW (not a broker microstructure fill engine).
2. Quantity is still operator-requested; risk sizing lives in scaled notional — by explicit contract, not silent conversion.
3. Schema still uses TEXT numeric fields; no new columns for scaled_notional (stored in JSON economics).
4. Orchestrator tracking stub still immediately closes when a price exists; without price it skips ledger write.

---

## 10. Rollback strategy

Revert MW-004 commit(s) on `css-v1.0.1-maintenance`.

---

## 11. Final recommendation

**READY_TO_COMMIT**

Do not push until explicit approval. Do not start CSS. Do not touch desktop.

---

*End of CSS_V1_0_1_MAINTENANCE_004_PAPER_LEDGER_FIDELITY_AUDIT.md*
