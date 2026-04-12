# CSS Futures Dashboard PnL Display - Master Specification
## Phase 1 Sandbox Futures Dashboard Visibility Lock

### Purpose
Defines dashboard display rules for futures PnL visibility inside CSS live dashboard.

This specification governs:

- per-futures-position unrealized PnL display
- per-futures-position realized PnL display
- aggregate futures portfolio PnL subtotal
- integration into dashboard cycle summary
- separation from crypto/fx/options PnL streams
- margin visibility for active futures positions

---

## Supported Scope (Phase 1)

### Futures Instruments:
- ES
- NQ
- CL

Sandbox only.

---

## Required Dashboard Display Sections

### 1. FUTURES OPEN POSITIONS PANEL

For every open futures position display:

- symbol
- side
- contracts
- entry price
- current price
- unrealized pnl
- margin reserved
- status

Example:

ES LONG x2 | Entry 5225.25 | Current 5229.75 | UPNL +450.00 | Margin 24000

---

### 2. FUTURES CLOSED POSITIONS PANEL

For closed futures positions display:

- symbol
- side
- contracts
- realized pnl
- exit reason

Example:

NQ SHORT x1 | RPNL +320.00 | target_hit

---

### 3. FUTURES SUBTOTAL LINE

Dashboard must show:

FUTURES TOTAL UPNL: xxx.xx  
FUTURES TOTAL RPNL: xxx.xx

---

### 4. GLOBAL PORTFOLIO SUMMARY INTEGRATION

Cycle summary must include:

- CRYPTO PNL
- FX PNL
- OPTIONS PNL
- FUTURES PNL
- TOTAL COMBINED PNL

---

## Calculation Rules

### Unrealized PnL

LONG:
(current - entry) × multiplier × contracts

SHORT:
(entry - current) × multiplier × contracts

### Realized PnL

LONG:
(exit - entry) × multiplier × contracts

SHORT:
(entry - exit) × multiplier × contracts

Apply:
- commissions
- slippage costs

---

## Contract Multipliers

- ES = 50
- NQ = 20
- CL = 1000

---

## Required Status Categories

Each futures row must classify as one of:

- OPEN
- PROFIT TARGET NEAR
- STOP LOSS NEAR
- MARGIN WARNING
- PARTIALLY CLOSED
- CLOSED
- FORCE LIQUIDATED

---

## Margin Visibility Rules

Dashboard must display:

- total futures margin reserved
- available simulated margin
- active margin warnings
- forced liquidation alert count

---

## Per-Symbol Exposure Block

Dashboard must include compact summary:

- ES: contracts open / margin reserved / unrealized pnl
- NQ: contracts open / margin reserved / unrealized pnl
- CL: contracts open / margin reserved / unrealized pnl

---

## Closed Trades Summary

Panel must also expose:

- total futures trades closed
- win count
- loss count
- average futures trade pnl
- forced liquidation count

---

## Data Sources Required

Dashboard reads from:

- futures_position_manager open positions state
- futures closed positions ledger
- futures audit ledger
- futures risk governor state

---

## Non-Regression Rule

This panel:
- must not alter existing crypto dashboard blocks
- must not remove current FX visibility
- must not remove current options visibility
- futures UI must remain additive only

---

## Laptop 1 Implementation Target

Primary file target:

scripts/css_live_dashboard.py

Secondary dependencies:
- futures_position_manager.py
- futures_audit_ledger.py
- futures_risk_governor.py

---

## Governance Status

Architecture locked.
Ready for Laptop 1 implementation after merge.
No production execution path modified.
