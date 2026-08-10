# Phase 198 — FX Blocker Reconciliation

**Baseline before governance refresh:** `9725802fb820628e66d1bcbb8c35c67f9a6a0b5d`
**Branch:** `css-rc-live-001-candidate`
**Scope:** governance reconciliation only
**Live trading authorized:** **NO**

## 1. Resolution

Phase 197 remediated `BLK-FX-CONVERSION` for the live micro-pilot capital-governance seam.

The implemented contract:

- requires explicit native notional currency for live orders;
- uses the governed `FXConversionProvider` contract for cross-currency normalization;
- normalizes the admission notional into CAD before CAD20 position and total-capital checks;
- fails closed when FX conversion is unavailable, unusable, mismatched, or invalid;
- retains conversion provenance in the approved decision;
- persists the exact approved CAD notional rather than the original native-currency amount;
- uses persisted CAD exposure for subsequent remaining-capital calculations.

Phase 197 validation completed with `3742 passed, 5 skipped, 0 failed`.

## 2. Governance effect

`BLK-FX-CONVERSION` is reclassified from `BLOCKED` to `RESOLVED`.

LDT-001 gate `D3 / available_capital_confirmed` is reclassified from `BLOCKED` to `PASS`
for the **offline governed capital-normalization contract only**.

## 3. Explicit non-claims

This phase does **not**:

- certify OANDA LIVE authentication, account access, market-data freshness, or order submission;
- clear `BLK-OANDA-LIVE`;
- clear `BLK-RC004-LIVE-UNLOCK`;
- designate a freeze SHA;
- issue founder live GO;
- start CSS runtime;
- contact any broker;
- access secrets;
- submit any order;
- authorize live trading.

The aggregate live posture therefore remains **NO-GO**.

## 4. Remaining independent blockers

- `BLK-OANDA-LIVE` — `BLOCKED`
- `BLK-RC004-LIVE-UNLOCK` — `BLOCKED`
- `BLK-FREEZE-SHA` — `NOT_TESTED`
- `BLK-FOUNDER-LIVE-GO` — `BLOCKED`
