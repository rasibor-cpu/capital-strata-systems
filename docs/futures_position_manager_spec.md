# CSS Futures Position Manager - Master Specification
## Phase 1 Sandbox Futures Position Governance Lock

### Purpose
Defines lifecycle control of futures positions inside CSS sandbox trading.

This specification governs:

- open futures position tracking
- long/short position state control
- partial close handling
- realized pnl booking
- unrealized pnl mark-to-market updates
- contract rollover preparation hooks
- position closure state transitions

---

## Supported Scope (Phase 1)

### Contracts:
- ES
- NQ
- CL

### Position Types:
- LONG futures
- SHORT futures

Sandbox only.

---

## Position Manager Responsibilities

Must support:

### 1. OPEN POSITION REGISTRATION
Store:
- position_id
- symbol
- side
- contracts
- entry_price
- open_timestamp

---

### 2. LIVE MARK-TO-MARKET UPDATES
For every market tick:

Update:
- current_price
- unrealized pnl
- tick movement delta

---

### 3. PARTIAL CLOSE SUPPORT

Example:
Open:
10 ES LONG

Close:
4 ES

Remaining:
6 ES active

Must preserve:
same position_id lineage

---

### 4. FULL CLOSE SUPPORT

When remaining contracts = 0:
Position status becomes:
CLOSED

Store:
- close timestamp
- realized pnl final

---

### 5. REALIZED PNL FORMULA

LONG:
(exit - entry) × multiplier × contracts

SHORT:
(entry - exit) × multiplier × contracts

Apply:
minus commissions
minus slippage costs

---

### 6. UNREALIZED PNL FORMULA

LONG:
(current - entry) × multiplier × open contracts

SHORT:
(entry - current) × multiplier × open contracts

---

## Contract Multipliers

ES:
50

NQ:
20

CL:
1000

---

## Position States

Valid states:

1. OPEN
2. PARTIALLY_CLOSED
3. CLOSED
4. ROLLED
5. FORCE_CLOSED_MARGIN

---

## Margin Event Hooks

Must support trigger flags:

- margin_warning
- maintenance_breach
- forced_liquidation_triggered

---

## Rollover Preparation Hook

Future-ready hook required:

roll_contract(
old_symbol,
new_symbol
)

No live rollover in Phase 1.

Preparation only.

---

## Event Outputs

Emit:

- POSITION_OPENED
- POSITION_UPDATED
- POSITION_PARTIAL_CLOSE
- POSITION_CLOSED
- POSITION_MARGIN_FORCED_CLOSE
- POSITION_ROLLED

---

## Integration Targets

Feeds:

1. futures_execution_adapter.py
2. futures_risk_governor.py
3. futures_dashboard_pnl_renderer
4. trade_decision_orchestrator.py

---

## Status

- Architecture locked
- Sandbox lifecycle governance only
- No broker live execution path modified
- Safe for Laptop 1 implementation conversion
