# CSS Options Dashboard PnL Display - Master Specification
## Phase 1 Sandbox Dashboard Profit Visibility Lock

### Purpose
Defines dashboard display rules for options PnL visibility inside CSS live dashboard.

This specification governs:

- per-option-position unrealized PnL display
- per-option-position realized PnL display
- aggregate options portfolio PnL subtotal
- integration into dashboard cycle summary
- separation from crypto/fx/futures PnL streams

---

## Required Dashboard Display Sections

### 1. OPTIONS OPEN POSITIONS PANEL

For every open option position display:

- symbol
- option type
- strike
- expiry
- contracts
- entry premium
- current premium
- unrealized pnl

Example:

AAPL CALL 210 14d x2 | Entry 4.20 | Current 5.05 | UPNL +170.00

---

### 2. OPTIONS CLOSED POSITIONS PANEL

For closed positions display:

- symbol
- option type
- realized pnl
- exit reason

Example:

SPY PUT 590 | CLOSED | RPNL +84.00 | target_hit

---

### 3. OPTIONS SUBTOTAL LINE

Dashboard must show:

OPTIONS TOTAL UPNL: xxx.xx
OPTIONS TOTAL RPNL: xxx.xx

---

### 4. GLOBAL PORTFOLIO SUMMARY INTEGRATION

Cycle summary must include:

CRYPTO PNL
FX PNL
FUTURES PNL
OPTIONS PNL
TOTAL COMBINED PNL

---

## Calculation Rules

### Unrealized PnL:

(current premium - entry premium) × contracts × 100

### Realized PnL:

(exit premium - entry premium) × contracts × 100

---

## Non-Regression Rule

Must not alter:

- existing crypto pnl display
- futures pnl display
- fx pnl display
- trade cycle numbering

Options display layer must be additive only.

---

## Implementation Target

Primary dashboard file:

scripts/css_live_dashboard.py

Data source:

backend/options/options_position_manager.py

---

## Status

Architecture approved.
Safe for implementation after Laptop 1 coding session.
