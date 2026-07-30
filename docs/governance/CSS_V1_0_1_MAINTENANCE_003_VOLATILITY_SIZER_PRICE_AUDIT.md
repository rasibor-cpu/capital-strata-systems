# CSS v1.0.1 — Maintenance Workstream 003
## RR-003 VolatilityPositionSizer Canonical Price Propagation

**Programme:** CSS v1.0.1 Maintenance
**Workstream:** MW-003 / RR-003
**Status:** IMPLEMENTED — VALIDATED — AWAITING COMMIT APPROVAL
**Workspace:** Laptop (`C:\rasib\source\capital-strata-systems`)
**Branch:** `css-v1.0.1-maintenance`
**HEAD (base, verified pre-implementation):** `3de9307394397c0dce43b419ce830dde9f3af77c`
**Date:** 2026-07-30
**Does not authorize:** live trading, OV-002, production deployment, desktop interference

---

## 1. Confirmed root cause

ExecutionGate volatility sizing omitted canonical `price` from `_vol_size` / `evaluate_trade`, while `VolatilityPositionSizer.size(notional, price)` requires `price`. Normal path relied on TypeError fallback to unscaled base notional and could still ALLOW.

**Classification:** H. Mixed (ExecutionGate wiring + sizer contract) — confirmed.

---

## 2. Final canonical-price contract

`ExecutionGate.evaluate_trade` accepts optional price fields and validates before volatility sizing. Validated `price` is passed to `_vol_size` → `VolatilityPositionSizer.size(notional=..., price=..., debug=...)`.

Missing/invalid/stale/mismatched prices return **BLOCK** with machine-readable reasons. No silent base-notional ALLOW.

---

## 3. Field / source precedence

First finite positive candidate wins:

1. `price`
2. `last_price`
3. `market_price`
4. `mid_price`
5. `reference_price`
6. `current_price`

Mobile ticket helper additionally allows **ticket-implied** `amount / qty` when both are finite and > 0 (no network fetch; instrument from ticket).

Optional metadata:

- `price_instrument` — must match `instrument` when provided
- `price_as_of` + `price_max_age_seconds` — freshness contract when both enforceable

---

## 4. Validation rules

Usable price must be:

- numeric (coercible to float)
- finite
- greater than zero
- instrument-matched when `price_instrument` supplied
- within max age when freshness metadata is supplied

---

## 5. Missing-price policy

`volatility_price_missing` → gate **BLOCK** (no ALLOW; no TypeError control flow).

---

## 6. Invalid-price policy

`volatility_price_invalid` for zero, negative, NaN, ±inf, malformed strings.

`VolatilityPositionSizer` raises `VolatilityPriceError` on invalid direct calls (no permissive mult=1.0 for bad prices). Warm-up mult=1.0 remains only for **valid** prices with insufficient history.

---

## 7. Stale-price policy

When `price_max_age_seconds` is set:

- missing/unparseable `price_as_of` → `volatility_price_stale` (fail-closed)
- age outside `[0, max_age]` → `volatility_price_stale`

Instrument mismatch → `volatility_price_instrument_mismatch`.

---

## 8. Files changed

| File | Change |
| --- | --- |
| `engine/risk/canonical_volatility_price.py` | **New** validation / precedence helpers |
| `engine/risk/volatility_position_sizer.py` | Reject invalid prices; warm-up preserved for valid |
| `engine/execution/execution_gate.py` | Canonical price args; fail-closed vol pricing; direct sizer call |
| `dashboard/mobile/mobile_app.py` | Resolve + pass ticket/market price to gate |
| `engine/engine_loop.py` | Pass bar `price` into gate |
| `engine/adapters/super_execution_gate_adapter.py` | Propagate price from market/equity context |
| `backend/app/headless_guarded_entry.py` | Propagate req/env price |
| `tests/test_mw003_volatility_sizer_price.py` | **New** MW-003 matrix |
| `tests/test_antibleed_guard_integration.py` | Supply valid price |
| `tests/test_margin_trade_gate_enforcement_integration.py` | Supply valid price |
| `tests/engine/test_risk_governor.py` | Supply valid price |
| `tests/engine/test_stock_alerts_runtime_integration.py` | Supply valid price |
| `tests/mobile/test_mobile_paper_expected_value_fallback.py` | Assert price kwargs |
| `engine/testing/run_drawdown_stress.py` | Supply valid price |
| `docs/governance/CSS_V1_0_1_MAINTENANCE_003_VOLATILITY_SIZER_PRICE_AUDIT.md` | This record |

---

## 9. Call sites updated

- Mobile paper/live gate invocation
- Engine loop signal evaluation
- Super execution gate adapter
- Headless guarded entry
- Deterministic gate test fixtures / stress harness

---

## 10. Tests added

`tests/test_mw003_volatility_sizer_price.py` covers valid price ALLOW, high-vol compression, warm-up, missing/invalid/NaN/inf, stale, instrument mismatch, FX/crypto, mobile implied price, live micro BLOCK, no TypeError path.

---

## 11. Validation results

| Suite | Result |
| --- | --- |
| `tests/test_mw003_volatility_sizer_price.py` | **18 passed** |
| AntiBleed + margin + risk governor + live authority + mobile paper/kill-switch + engine loop wiring | **57 passed** (combined run) |
| `git diff --check` | PASS after EOF trim |

Env cleared: `CSS_ENV`, `DEFAULT_EXECUTION_MODE`, `CSS_RUNTIME_MODE`, `ENGINE_MODE`.

CSS not started. Desktop not accessed.

---

## 12. Safety verification

- AntiBleedGuard and MarginTradeGate unchanged in thresholds; still evaluated before vol sizing
- Invalid/missing price cannot ALLOW
- No invented prices (0/1/stale/unrelated instrument)
- No broker/credential/authority/threshold changes

---

## 13. Live-authority verification

- `test_phase153i_live_execution_authority.py` passed
- Live missing anti-bleed microstructure still BLOCK
- Live trading not authorized

---

## 14. Remaining limitations

1. Mobile paper ledger still persists `entry_price=0.0` and quantity = ticket qty (not vol-scaled). **Residual — out of MW-003 bound.**
2. Ticket-implied `amount/qty` is used when no explicit market last is on the ticket; it is ticket-owned, not an external MD fetch.
3. Freshness is enforced only when callers supply `price_max_age_seconds` (and timestamp).
4. Diagnostic/incomplete headless probes without price now BLOCK on volatility price reasons after other gates — non-authorizing (correct).

---

## 15. Residual risks

| ID | Item | Priority |
| --- | --- | --- |
| RR-003b | Mobile ledger `entry_price=0.0` / qty not reconciled to gate scaled notional | P3 follow-on |
| RR-004 | Open-trade uniqueness messaging (unchanged) | P3 |

---

## 16. Rollback strategy

Revert MW-003 commit(s) on `css-v1.0.1-maintenance`. Behavior returns to missing-price TypeError fallback. No schema migration.

---

## 17. Final recommendation

**READY_TO_COMMIT**

Do not push until explicit approval. Do not start CSS. Do not touch desktop.

---

*End of CSS_V1_0_1_MAINTENANCE_003_VOLATILITY_SIZER_PRICE_AUDIT.md*
